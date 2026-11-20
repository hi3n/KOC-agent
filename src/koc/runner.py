"""Generic stage runner — tasks table driven, idempotent, resumable.

Reliability contract (ARCHITECTURE.md §6):
- item = (run_id, stage, entity_id); only pending/eligible-waiting items run.
- stale 'running' reset to 'pending' at startup (crash recovery).
- paid results land in api_cache/judgements BEFORE task status flips to done;
  a kill in between re-runs the item as a cache hit -> zero extra cost.
- WaitingKalodata(1054) -> waiting + exponential backoff; VideoMissing(1053) ->
  failed terminal; other errors retry up to 3 attempts, never block siblings.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Callable

from .db import Database
from .kalodata import VideoMissing, WaitingKalodata
from .ledger import Ledger

MAX_ATTEMPTS = 3
WAIT_BACKOFF_BASE = 15.0


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _eligible(row: dict) -> bool:
    if row["status"] == "pending":
        return True
    if row["status"] == "waiting_kalodata":
        backoff = min(300.0, WAIT_BACKOFF_BASE * (2 ** row["attempts"]))
        updated = datetime.fromisoformat(row["updated_at"]).replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - updated).total_seconds() >= backoff
    return False


class StageRunner:
    def __init__(self, db: Database, ledger: Ledger, run_id: str):
        self.db, self.ledger, self.run_id = db, ledger, run_id
        self.on_progress: Callable[[str, int, int, str], None] | None = None

    def ensure_tasks(self, stage: str, items: list[str]):
        with self.db.transaction() as conn:
            for it in items:
                conn.execute(
                    "INSERT OR IGNORE INTO tasks (run_id, stage, entity_id, status)"
                    " VALUES (?,?,?,'pending')", (self.run_id, stage, it))

    def reset_stale(self, stage: str):
        self.db.execute(
            "UPDATE tasks SET status='pending', updated_at=? WHERE run_id=? AND stage=?"
            " AND status='running'", (_now(), self.run_id, stage))

    def pending_items(self, stage: str) -> list[str]:
        rows = self.db.query(
            "SELECT * FROM tasks WHERE run_id=? AND stage=? AND status IN"
            " ('pending','waiting_kalodata') ORDER BY entity_id", (self.run_id, stage))
        return [r["entity_id"] for r in rows if _eligible(r)]

    def done_results(self, stage: str) -> dict[str, dict]:
        # ORDER BY entity_id: thứ tự dict KHÔNG phụ thuộc completion order —
        # kill/resume phải ra cùng batch composition, cùng hash, cùng kết quả (19/11)
        rows = self.db.query(
            "SELECT entity_id, result_json FROM tasks WHERE run_id=? AND stage=? AND status='done'"
            " ORDER BY entity_id", (self.run_id, stage))
        return {r["entity_id"]: json.loads(r["result_json"]) if r["result_json"] else {} for r in rows}

    def run(self, stage: str, items: list[str], worker, concurrency: int = 8,
            on_done=None) -> dict:
        """worker(entity_id) -> result dict (stored in tasks.result_json).
        Returns {done, failed, waiting, skipped}. on_done(entity_id, result) optional
        callback executed in caller thread after each success (for progress logs)."""
        self.ensure_tasks(stage, items)
        self.reset_stale(stage)
        summary = {"done": 0, "failed": 0, "waiting": 0, "skipped": 0}
        unique_items = list(dict.fromkeys(items))
        total = len(unique_items)
        done_count = 0
        if total and self.on_progress:
            ph = ",".join("?" * total)
            done_row = self.db.one(
                f"SELECT COUNT(*) n FROM tasks WHERE run_id=? AND stage=? AND status='done' AND entity_id IN ({ph})",
                (self.run_id, stage, *unique_items),
            )
            done_count = done_row["n"] if done_row else 0
        lock = threading.Lock()
        while True:
            eligible = self.pending_items(stage)
            if not eligible:
                # waiting items with future backoff? sleep until earliest due, else finish
                rows = self.db.query(
                    "SELECT updated_at, attempts FROM tasks WHERE run_id=? AND stage=?"
                    " AND status='waiting_kalodata'", (self.run_id, stage))
                if not rows:
                    break
                waits = []
                for r in rows:
                    backoff = min(300.0, WAIT_BACKOFF_BASE * (2 ** r["attempts"]))
                    updated = datetime.fromisoformat(r["updated_at"]).replace(tzinfo=timezone.utc)
                    elapsed = (datetime.now(timezone.utc) - updated).total_seconds()
                    waits.append(max(0.01, backoff - elapsed))
                time.sleep(min(waits))
                continue
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {pool.submit(self._run_item, stage, it, worker): it for it in eligible}
                for fut in as_completed(futures):
                    it = futures[fut]
                    status, result = fut.result()
                    emit = None
                    with lock:
                        summary[status] = summary.get(status, 0) + 1
                        if status == "done":
                            done_count += 1
                        if status == "done" and self.on_progress and total > 0 and (
                            stage in ("s4_media", "s4_judge")
                            or done_count == total
                            or done_count % 5 == 0
                        ):
                            emit = (stage, done_count, total, status)
                    if emit:
                        self.on_progress(*emit)
                    if status == "done" and on_done:
                        on_done(it, result)
        return summary

    def _run_item(self, stage: str, entity_id: str, worker):
        self.db.execute(
            "UPDATE tasks SET status='running', attempts=attempts+1, updated_at=?"
            " WHERE run_id=? AND stage=? AND entity_id=?",
            (_now(), self.run_id, stage, entity_id))
        try:
            result = worker(entity_id)
            with self.db.transaction() as conn:
                conn.execute(
                    "UPDATE tasks SET status='done', result_json=?, error=NULL, updated_at=?"
                    " WHERE run_id=? AND stage=? AND entity_id=?",
                    (json.dumps(result, ensure_ascii=False, default=str), _now(),
                     self.run_id, stage, entity_id))
            return "done", result
        except WaitingKalodata as e:
            self.db.execute(
                "UPDATE tasks SET status='waiting_kalodata', error=?, updated_at=?"
                " WHERE run_id=? AND stage=? AND entity_id=?",
                (str(e), _now(), self.run_id, stage, entity_id))
            return "waiting", None
        except VideoMissing as e:
            self.db.execute(
                "UPDATE tasks SET status='failed', error=?, updated_at=?"
                " WHERE run_id=? AND stage=? AND entity_id=?",
                (f"1053 {e}", _now(), self.run_id, stage, entity_id))
            return "failed", None
        except Exception as e:
            row = self.db.one("SELECT attempts FROM tasks WHERE run_id=? AND stage=? AND entity_id=?",
                              (self.run_id, stage, entity_id))
            attempts = row["attempts"] if row else 1
            status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
            self.db.execute(
                "UPDATE tasks SET status=?, error=?, updated_at=?"
                " WHERE run_id=? AND stage=? AND entity_id=?",
                (status, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}",
                 _now(), self.run_id, stage, entity_id))
            return ("failed" if status == "failed" else "waiting"), None
