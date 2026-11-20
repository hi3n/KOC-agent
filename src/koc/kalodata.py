"""Kalodata connector — the single gate for every paid API call.

cached_call + token-bucket rate limit + backoff retry + typed error codes
(1053 video missing / 1054 video queued) + fixture record/replay + ledger.
Paths confirmed against public OpenAPI spec: /openapi/v1/tiktok/<endpoint>.
"""
from __future__ import annotations

import json
import random
import threading
import time
import zlib
from pathlib import Path

import httpx

from .config import canonical_hash
from .db import Database
from .ledger import Ledger

# Credit estimates per call (rank: 0.1 x ceil(rows/100), page_size<=100 -> 0.1).
# Calibrated against credit/balance in spike; adjust here if reality differs.
CREDITS = {
    "category/rank": 0.1, "category/detail": 0.1,
    "creator/rank": 0.1, "creator/detail": 0.1,
    "video/rank": 0.1, "video/detail": 0.1, "video/url": 0.5,
}


class KalodataError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(f"kalodata code={code}: {message}")


class WaitingKalodata(KalodataError):
    """1054: video not stored yet, retry later."""


class VideoMissing(KalodataError):
    """1053: video does not exist."""


class OfflineMiss(Exception):
    """Replay mode and no fixture for this call."""


class _Retryable(Exception):
    """Envelope-level transient error (2017 traffic control) — retry with backoff."""


class _Bucket:
    def __init__(self, rate: float, per: float = 10.0):
        self.rate, self.per = rate, per
        self.tokens = rate
        self.ts = time.monotonic()
        self.lock = threading.Lock()

    def acquire(self):
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.rate, self.tokens + (now - self.ts) * self.rate / self.per)
                self.ts = now
                if self.tokens >= 1:
                    self.tokens -= 1
                    return
                wait = (1 - self.tokens) * self.per / self.rate
            time.sleep(wait)


class KalodataClient:
    def __init__(self, db: Database, ledger: Ledger, cfg: dict, api_key: str,
                 mode: str = "rw", fixtures_dir: str | Path = "fixtures",
                 date_range: str = "", governor=None):
        self.db, self.ledger, self.cfg = db, ledger, cfg
        self.mode = mode
        self.governor = governor
        self.fixtures = Path(fixtures_dir)
        self.fixtures.mkdir(parents=True, exist_ok=True)
        self.date_range = date_range
        self.bucket = _Bucket(float(cfg.get("rate_per_10s", 90)))
        self.http = httpx.Client(
            base_url=cfg.get("base_url", "https://www.kalodata.com"),
            timeout=float(cfg.get("timeout_s", 60)),
            headers={"X-API-Key": api_key, "Content-Type": "application/json"})
        self._inflight: dict[str, threading.Event] = {}
        self._inflight_lock = threading.Lock()
        if mode == "replay":
            self._load_fixtures()

    # ---------- public ----------
    def call(self, endpoint: str, params: dict, stage: str, ttl: int | None = None) -> dict:
        """Return envelope['data']. ttl=None means immutable (pinned date range)."""
        params = self._normalize(params)
        key = canonical_hash([endpoint, params])
        row = self.db.one("SELECT body_zlib, fetched_at, ttl_seconds FROM api_cache WHERE key=?", (key,))
        if row and self.mode != "refresh" and self._fresh(row, ttl):
            self.ledger.log("kalodata", stage, cache_hit=True, note=endpoint)
            return json.loads(zlib.decompress(row["body_zlib"]))
        if self.mode == "replay":
            raise OfflineMiss(f"{endpoint} {key[:12]}")

        # in-flight dedupe: concurrent tasks needing same key pay once
        with self._inflight_lock:
            ev = self._inflight.get(key)
            owner = ev is None
            if owner:
                ev = threading.Event()
                self._inflight[key] = ev
        if not owner:
            ev.wait(timeout=120)
            return self.call(endpoint, params, stage, ttl)  # now a cache hit

        try:
            if self.governor is not None:
                est_cr = CREDITS.get(endpoint, 0.1)
                ok, gmsg = self.governor.check_kalodata_call(stage, endpoint, est_credits=est_cr)
                if not ok:
                    raise KalodataError("GOVERNOR_BLOCKED", gmsg)
            t0 = time.perf_counter()
            envelope = self._fetch(endpoint, params)
            latency = int((time.perf_counter() - t0) * 1000)
            data = envelope.get("data")
            credits = CREDITS.get(endpoint, 0.1)
            body = json.dumps(data, ensure_ascii=False).encode()
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO api_cache (key, endpoint, params_json, body_zlib,"
                    " fetched_at, ttl_seconds, credits) VALUES (?,?,?,?,datetime('now'),?,?)",
                    (key, endpoint, json.dumps(params, sort_keys=True, ensure_ascii=False),
                     zlib.compress(body), ttl, credits))
            self.ledger.log("kalodata", stage, credits=credits, latency_ms=latency,
                            note=f"{endpoint} cached={envelope.get('cached')}")
            self._write_fixture(endpoint, params, key, envelope)
            return data
        finally:
            with self._inflight_lock:
                self._inflight.pop(key, None)
            ev.set()

    def cache_key(self, endpoint: str, params: dict) -> str:
        return canonical_hash([endpoint, self._normalize(params)])

    def balance(self) -> dict:
        r = self.http.get("/openapi/v1/credit/balance")
        r.raise_for_status()
        return r.json()

    def base_params(self, **extra) -> dict:
        p = {"region": self.cfg.get("region", "VN"),
             "language": self.cfg.get("language", "vi-VN"),
             "currency": self.cfg.get("currency", "VND"),
             "date_range": self.date_range}
        p.update({k: v for k, v in extra.items() if v is not None})
        return p

    # ---------- internals ----------
    def _normalize(self, params: dict) -> dict:
        return {k: v for k, v in sorted(params.items()) if v is not None}

    def _fresh(self, row: dict, ttl: int | None) -> bool:
        effective = row["ttl_seconds"] if row["ttl_seconds"] is not None else ttl
        if effective is None:
            return True  # immutable
        from datetime import datetime, timezone
        fetched = datetime.fromisoformat(row["fetched_at"]).replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - fetched).total_seconds()
        return age < effective

    def _fetch(self, endpoint: str, params: dict) -> dict:
        path = f"/openapi/v1/tiktok/{endpoint}"
        last_err: Exception | None = None
        for attempt in range(4):
            self.bucket.acquire()
            try:
                r = self.http.post(path, json=params)
                if r.status_code == 429 or r.status_code >= 500:
                    raise httpx.HTTPStatusError(f"status {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                env = r.json()
                if env.get("success"):
                    return env
                code = env.get("code")
                msg = env.get("message", "")
                if code == 1054:
                    raise WaitingKalodata(code, msg)
                if code == 1053:
                    raise VideoMissing(code, msg)
                # spike 19/11: rate limit tới trong envelope (2017), không phải HTTP 429
                if code == 2017 or "traffic control" in str(msg).lower():
                    raise _Retryable(f"code={code}: {msg}")
                raise KalodataError(code, msg)
            except (httpx.TransportError, httpx.HTTPStatusError, _Retryable) as e:
                last_err = e
                if attempt < 3:
                    time.sleep(2 * (2 ** attempt) + random.random() * 2)
        raise KalodataError(None, f"transport/traffic failed after retries: {last_err}")

    def _write_fixture(self, endpoint: str, params: dict, key: str, envelope: dict):
        slug = endpoint.replace("/", "_")
        p = self.fixtures / f"{slug}__{key[:12]}.json"
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"endpoint": endpoint, "params": params,
                                   "envelope": envelope}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        tmp.replace(p)

    def _load_fixtures(self):
        n = 0
        bundle = self.fixtures / "judgements_bundle.json"
        if bundle.exists():
            try:
                obj = json.loads(bundle.read_text(encoding="utf-8"))
                for j in obj.get("judgements", []):
                    self.db.execute(
                        "INSERT OR IGNORE INTO judgements (judgement_id, run_id, stage, entity_id,"
                        " model, prompt_version, rubric_version, state_hash, output_json, attempts)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (j["judgement_id"], j["run_id"], j["stage"], j["entity_id"], j["model"],
                         j["prompt_version"], j["rubric_version"], j["state_hash"],
                         j["output_json"], j.get("attempts", 1)))
                for v in obj.get("videos", []):
                    # remap to current run so replay finds file_hash for judge cache keys
                    self.db.execute(
                        "INSERT OR IGNORE INTO videos (run_id, video_id, creator_id, role, file_path,"
                        " file_hash, bytes, duration_s, transcript_path, frames_json, status)"
                        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                        (self.ledger.run_id, v["video_id"], v["creator_id"], v["role"], v["file_path"],
                         v["file_hash"], v["bytes"], v["duration_s"], v["transcript_path"],
                         v["frames_json"], v["status"]))
            except Exception:
                pass
        for p in self.fixtures.glob("*__*.json"):
            try:
                obj = json.loads(p.read_text(encoding="utf-8"))
                key = canonical_hash([obj["endpoint"], self._normalize(obj["params"])])
                body = json.dumps(obj["envelope"].get("data"), ensure_ascii=False).encode()
                self.db.execute(
                    "INSERT OR IGNORE INTO api_cache (key, endpoint, params_json, body_zlib,"
                    " fetched_at, ttl_seconds, credits) VALUES (?,?,?,?,datetime('now'),NULL,0)",
                    (key, obj["endpoint"], json.dumps(obj["params"], sort_keys=True), zlib.compress(body)))
                n += 1
            except Exception:
                continue
        self._fixtures_loaded = n

    def close(self):
        self.http.close()
