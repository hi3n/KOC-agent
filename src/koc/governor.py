"""Code-side Governor: hard budget/time/replan/loop guardrails + decision audit log.

Every autonomous planner action or human approval passes through here and is recorded
into the SQLite `decisions` table (both allowed and blocked actions).
"""
from __future__ import annotations

import json
import time

from .db import Database
from .ledger import Ledger

ALLOWED_ACTIONS = frozenset({
    "proceed",
    "expand_candidates",
    "fetch_video_urls",
    "inspect_extra_video",
    "relax_constraints",
    "select_portfolio",
    "report_infeasible",
    "vision_reroute",
    "human_approval",
    "llm_call",
    "kalodata_call",
})

REPLAN_ACTIONS = frozenset({"expand_candidates", "inspect_extra_video", "relax_constraints"})


class Governor:
    """Enforces hard ceilings in code so the agent cannot loop or overspend."""

    def __init__(self, db: Database, ledger: Ledger, run_id: str, limits: dict | None = None):
        self.db = db
        self.ledger = ledger
        self.run_id = run_id
        lim = limits or {}
        self.credit_budget = float(lim.get("credit_budget", 13.0))
        self.max_ai_usd = float(lim.get("max_ai_usd", 5.0))
        self.max_tokens = int(lim.get("max_tokens", 1_500_000))
        self.max_wall_seconds = float(lim.get("max_wall_seconds", 1800.0))
        self.max_replans = int(lim.get("max_replans", 3))
        self.started_at = time.monotonic()
        self._seen_actions: set[tuple[str, str]] = set()
        self._replans = 0
        for r in self.db.query(
            "SELECT action, COALESCE(target,'') AS target FROM decisions"
            " WHERE run_id=? AND allowed=1 AND actor='planner'",
            (self.run_id,),
        ):
            if r["action"] in REPLAN_ACTIONS:
                self._seen_actions.add((r["action"], r["target"]))
                self._replans += 1

    def record(self, stage: str, actor: str, action: str, target: str = "",
               allowed: bool = True, reason: str = "", payload: dict | None = None) -> dict:
        pjson = json.dumps(payload, ensure_ascii=False, default=str) if payload else None
        if actor != "human":
            self.db.execute(
                "DELETE FROM decisions WHERE run_id=? AND stage=? AND actor=? AND action=?"
                " AND COALESCE(target,'')=? AND allowed=?",
                (self.run_id, stage, actor, action, target or "", int(allowed)),
            )
        self.db.execute(
            "INSERT INTO decisions (run_id, stage, actor, action, target, allowed, reason, payload_json)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (self.run_id, stage, actor, action, target, int(allowed), reason, pjson),
        )
        return {
            "stage": stage, "actor": actor, "action": action,
            "target": target, "allowed": allowed, "reason": reason,
        }

    def authorize(self, stage: str, action: str, *, target: str = "", actor: str = "planner",
                  est_credits: float = 0.0, est_usd: float = 0.0, est_tokens: int = 0,
                  is_replan: bool = False, reason: str = "",
                  payload: dict | None = None) -> tuple[bool, str]:
        ok = True
        final_reason = reason
        if action not in ALLOWED_ACTIONS:
            ok = False
            final_reason = f"BLOCKED: action '{action}' not in allowlist"
        elif is_replan and (action, target) in self._seen_actions:
            ok = False
            final_reason = f"BLOCKED: duplicate replan action ({action}, {target}) — anti-loop"
        elif is_replan and self._replans >= self.max_replans:
            ok = False
            final_reason = f"BLOCKED: max_replans ({self.max_replans}) reached"
        elif time.monotonic() - self.started_at > self.max_wall_seconds:
            ok = False
            final_reason = f"BLOCKED: max_wall_seconds ({self.max_wall_seconds:.0f}s) exceeded"
        elif est_credits > 0 and self.ledger.credits_used() + est_credits > self.credit_budget + 1e-9:
            used = self.ledger.credits_used()
            ok = False
            final_reason = (
                f"BLOCKED: credit_budget {self.credit_budget:.1f}cr exceeded "
                f"(used {used:.1f}cr + est {est_credits:.1f}cr)"
            )
        elif est_usd > 0 and self.ledger.ai_cost_usd() + est_usd > self.max_ai_usd + 1e-9:
            used_usd = self.ledger.ai_cost_usd()
            ok = False
            final_reason = (
                f"BLOCKED: max_ai_usd ${self.max_ai_usd:.2f} exceeded "
                f"(used ${used_usd:.4f} + est ${est_usd:.4f})"
            )
        elif est_tokens > 0 and self.ledger.tokens_used() + est_tokens > self.max_tokens:
            used_tok = self.ledger.tokens_used()
            ok = False
            final_reason = (
                f"BLOCKED: max_tokens {self.max_tokens:,} exceeded "
                f"(used {used_tok:,} + est {est_tokens:,})"
            )

        if ok and is_replan:
            self._replans += 1
            self._seen_actions.add((action, target))

        self.record(stage, actor, action, target=target, allowed=ok,
                    reason=final_reason, payload=payload)
        return ok, final_reason

    def check_llm_call(self, stage: str, entity_id: str, est_usd: float = 0.0,
                       est_tokens: int = 0) -> tuple[bool, str]:
        """Chốt chặn runtime trước mọi lời gọi LLM live (chỉ ghi `decisions` khi chặn)."""
        msg = ""
        if time.monotonic() - self.started_at > self.max_wall_seconds:
            msg = f"BLOCKED: max_wall_seconds ({self.max_wall_seconds:.0f}s) exceeded"
        else:
            used_usd = self.ledger.ai_cost_usd()
            if used_usd >= self.max_ai_usd - 1e-9 or (est_usd > 0 and used_usd + est_usd > self.max_ai_usd + 1e-9):
                msg = (
                    f"BLOCKED: max_ai_usd ${self.max_ai_usd:.2f} exceeded "
                    f"(used ${used_usd:.4f} + est ${est_usd:.4f})"
                )
            else:
                used_tok = self.ledger.tokens_used()
                if used_tok >= self.max_tokens or (est_tokens > 0 and used_tok + est_tokens > self.max_tokens):
                    msg = (
                        f"BLOCKED: max_tokens {self.max_tokens:,} exceeded "
                        f"(used {used_tok:,} + est {est_tokens:,})"
                    )
        if msg:
            self.record(stage, "governor", "llm_call", target=f"{stage}:{entity_id}",
                        allowed=False, reason=msg)
            return False, msg
        return True, ""

    def check_kalodata_call(self, stage: str, endpoint: str, est_credits: float = 0.1) -> tuple[bool, str]:
        """Chốt chặn runtime trước mọi lời gọi Kalodata live (chỉ ghi `decisions` khi chặn)."""
        msg = ""
        if time.monotonic() - self.started_at > self.max_wall_seconds:
            msg = f"BLOCKED: max_wall_seconds ({self.max_wall_seconds:.0f}s) exceeded"
        else:
            used_cr = self.ledger.credits_used()
            if est_credits > 0 and used_cr + est_credits > self.credit_budget + 1e-9:
                msg = (
                    f"BLOCKED: credit_budget {self.credit_budget:.1f}cr exceeded "
                    f"(used {used_cr:.1f}cr + est {est_credits:.1f}cr)"
                )
        if msg:
            self.record(stage, "governor", "kalodata_call", target=f"{stage}:{endpoint}",
                        allowed=False, reason=msg)
            return False, msg
        return True, ""

    def decisions(self) -> list[dict]:
        return self.db.query(
            "SELECT ts, stage, actor, action, target, allowed, reason, payload_json"
            " FROM decisions WHERE run_id=? ORDER BY id",
            (self.run_id,),
        )
