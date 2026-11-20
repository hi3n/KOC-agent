"""SQLite WAL store: cache, tasks, judgements, evidence, videos, ledger, runs.

One connection + RLock (single process, thread pool workers). Writes are short;
every item's results + task status + ledger commit in ONE transaction so kill -9
never leaves half-state.
"""
from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  config_json TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  status TEXT DEFAULT 'running',
  started_at TEXT DEFAULT (datetime('now')),
  finished_at TEXT
);

CREATE TABLE IF NOT EXISTS api_cache (
  key TEXT PRIMARY KEY,
  endpoint TEXT NOT NULL,
  params_json TEXT NOT NULL,
  body_zlib BLOB NOT NULL,
  fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
  ttl_seconds INTEGER,
  credits REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tasks (
  run_id TEXT, stage TEXT, entity_id TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER DEFAULT 0,
  updated_at TEXT DEFAULT (datetime('now')),
  error TEXT,
  result_json TEXT,
  PRIMARY KEY (run_id, stage, entity_id)
);

CREATE TABLE IF NOT EXISTS judgements (
  judgement_id TEXT PRIMARY KEY,
  run_id TEXT, stage TEXT, entity_id TEXT,
  model TEXT, prompt_version TEXT, rubric_version TEXT,
  state_hash TEXT, output_json TEXT,
  evidence_ids_json TEXT, valid INTEGER DEFAULT 1, attempts INTEGER DEFAULT 1,
  created_at TEXT DEFAULT (datetime('now')),
  UNIQUE(model, prompt_version, rubric_version, state_hash)
);

CREATE TABLE IF NOT EXISTS evidence (
  evidence_id TEXT PRIMARY KEY,
  run_id TEXT, creator_id TEXT, video_id TEXT,
  stage TEXT, kind TEXT, source_ref TEXT,
  payload_json TEXT,
  created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS videos (
  run_id TEXT, video_id TEXT, creator_id TEXT,
  role TEXT,
  file_path TEXT, file_hash TEXT, bytes INTEGER, duration_s REAL,
  transcript_path TEXT, frames_json TEXT,
  status TEXT DEFAULT 'pending',
  PRIMARY KEY (run_id, video_id)
);

CREATE TABLE IF NOT EXISTS usage_ledger (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT DEFAULT (datetime('now')),
  run_id TEXT, stage TEXT, provider TEXT,
  entity_id TEXT, cache_hit INTEGER DEFAULT 0,
  credits REAL DEFAULT 0, tokens_in INTEGER DEFAULT 0,
  tokens_out INTEGER DEFAULT 0, tokens_cached INTEGER DEFAULT 0,
  cost_usd REAL, latency_ms INTEGER DEFAULT 0, note TEXT
);

CREATE TABLE IF NOT EXISTS decisions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT DEFAULT (datetime('now')),
  run_id TEXT NOT NULL,
  stage TEXT NOT NULL,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  target TEXT,
  allowed INTEGER NOT NULL DEFAULT 1,
  reason TEXT,
  payload_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(run_id, stage, status);
CREATE INDEX IF NOT EXISTS idx_ledger_run ON usage_ledger(run_id, stage, provider);
CREATE INDEX IF NOT EXISTS idx_evidence_creator ON evidence(run_id, creator_id);
CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id, stage);
"""


class Database:
    def __init__(self, path: str | Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA synchronous=NORMAL")
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        with self.lock:
            cur = self.conn.execute(sql, params)
            self.conn.commit()
            return cur

    def query(self, sql: str, params: tuple | list = ()) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def one(self, sql: str, params: tuple | list = ()) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    @contextmanager
    def transaction(self):
        with self.lock:
            self.conn.execute("BEGIN IMMEDIATE")
            try:
                yield self.conn
                self.conn.commit()
            except Exception:
                self.conn.rollback()
                raise

    def reset_stale_running(self, run_id: str) -> int:
        """Crash recovery: process died mid-item -> those items run again.
        Count bằng SELECT trước (rowcount sau commit không đáng tin qua mọi driver path)."""
        rows = self.query("SELECT entity_id FROM tasks WHERE run_id=? AND status='running'", (run_id,))
        if rows:
            self.execute(
                "UPDATE tasks SET status='pending', updated_at=datetime('now') "
                "WHERE run_id=? AND status='running'", (run_id,))
        return len(rows)

    def reset_retryable_failed(self, run_id: str) -> int:
        """Transient failures (traffic control / transport) deserve another pass."""
        cur = self.execute(
            "UPDATE tasks SET status='pending', attempts=0, updated_at=datetime('now') "
            "WHERE run_id=? AND status='failed' AND (error LIKE '%2017%' OR error LIKE '%transport%')",
            (run_id,))
        return cur.rowcount

    def close(self):
        with self.lock:
            self.conn.close()
