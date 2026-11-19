"""Usage ledger — single source of truth for benchmark numbers.

Every paid call (Kalodata credit, LLM token) and every free local operation
(ASR, cache hit) lands here with stage/provider/entity, so cold vs warm runs,
funnel vs naive extrapolation and resume-cost proofs are SQL queries, not guesses.
"""
from __future__ import annotations

import time
from contextlib import contextmanager

from .db import Database


class Ledger:
    def __init__(self, db: Database, run_id: str):
        self.db = db
        self.run_id = run_id

    def log(self, provider: str, stage: str, *, entity_id: str | None = None,
            cache_hit: bool = False, credits: float = 0.0,
            tokens_in: int = 0, tokens_out: int = 0, tokens_cached: int = 0,
            cost_usd: float | None = None, latency_ms: int = 0,
            note: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO usage_ledger (run_id, stage, provider, entity_id, cache_hit,"
            " credits, tokens_in, tokens_out, tokens_cached, cost_usd, latency_ms, note)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (self.run_id, stage, provider, entity_id, int(cache_hit), credits,
             tokens_in, tokens_out, tokens_cached, cost_usd, latency_ms, note))

    @contextmanager
    def timed(self, provider: str, stage: str, **kw):
        t0 = time.perf_counter()
        holder: dict = {}
        try:
            yield holder
        finally:
            self.log(provider, stage, latency_ms=int((time.perf_counter() - t0) * 1000),
                     **{**kw, **holder})

    def rollup(self) -> list[dict]:
        return self.db.query(
            "SELECT stage, provider, COUNT(*) n_calls,"
            " SUM(cache_hit) hits, SUM(credits) credits,"
            " SUM(tokens_in) tin, SUM(tokens_out) tout, SUM(tokens_cached) tcached,"
            " SUM(cost_usd) cost, AVG(latency_ms) avg_ms, SUM(latency_ms) total_ms"
            " FROM usage_ledger WHERE run_id=? GROUP BY stage, provider"
            " ORDER BY stage, provider", (self.run_id,))

    def totals(self) -> dict:
        r = self.db.one(
            "SELECT SUM(credits) credits, SUM(tokens_in) tin, SUM(tokens_out) tout,"
            " SUM(tokens_cached) tcached, SUM(cost_usd) cost, SUM(latency_ms) ms,"
            " COUNT(*) n FROM usage_ledger WHERE run_id=?", (self.run_id,)) or {}
        return {k: (v or 0) for k, v in r.items()}

    def credits_used(self) -> float:
        r = self.db.one("SELECT SUM(c) c FROM (SELECT SUM(credits) c FROM usage_ledger"
                        " WHERE run_id=? AND provider='kalodata' AND cache_hit=0)",
                        (self.run_id,))
        return float(r["c"] or 0) if r else 0.0
