"""Provider-neutral LLM gate — OpenAI-compatible chat/completions, one client.

Works with any provider exposing that surface (Anthropic compat endpoint,
Gemini compat, OpenRouter, ollama/vLLM): role config carries base_url/api_key/
model/extra. Structured output via response_format=json_schema with automatic
fallback to json_object + pydantic validation + bounded retry. Every call is
cached (judgements table) and ledgered; cache hits never construct a client,
so offline replay needs no key.

Failover design (bounded, explicit — NOT a dynamic model router):
- chain = [primary role] + configured fallbacks (env/YAML, opt-in).
- fallback triggers only on real failure: auth/quota/model-not-found, transient
  errors after SDK retries, or schema-invalid after bounded attempts.
- every attempt + failover is ledgered; cache key includes the model actually
  used, so resume/replay stay consistent and cost attribution stays honest.
- all members fail -> LLMUnavailable; stages degrade explicitly (S0 -> YAML
  defaults, S3 -> code-only scores + flag, S5 -> evidence-template reasons).
Dynamic per-request model selection is deliberately NOT done: it fragments the
judgement cache, breaks resume determinism and benchmark attribution, and adds
an unmeasurable decision point (ARCHITECTURE.md D18).
"""
from __future__ import annotations

import json
import time
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from .config import LLMRole, canonical_hash
from .db import Database
from .ledger import Ledger

T = TypeVar("T", bound=BaseModel)


class LLMUnavailable(Exception):
    """Every configured provider failed for this call — stage must degrade."""


class GovernorBlocked(LLMUnavailable):
    """Governor runtime guardrail blocked live call (budget/tokens/wall-clock)."""


def _strict_schema(schema: type[BaseModel]) -> dict:
    """Pydantic JSON schema -> OpenAI strict json_schema (inline $defs,
    additionalProperties=false, all properties required)."""
    raw = schema.model_json_schema()
    defs = raw.pop("$defs", {})

    def inline(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                ref = node["$ref"].split("/")[-1]
                return inline(defs.get(ref, {}))
            out = {k: inline(v) for k, v in node.items() if k != "title"}
            if out.get("type") == "object" and "properties" in out:
                out["additionalProperties"] = False
                out["required"] = list(out["properties"].keys())
            return out
        if isinstance(node, list):
            return [inline(v) for v in node]
        return node

    return inline(raw)


def _cost(prices: dict, model: str, tin: int, tout: int, tcached: int) -> float | None:
    p = prices.get(model)
    if p is None:
        for k, v in prices.items():
            if model.endswith(k):
                p = v
                break
    if p is None:
        return None
    fresh = max(0, tin - tcached)
    return round((fresh * p.get("in", 0) + tcached * p.get("cache_read", p.get("in", 0))
                  + tout * p.get("out", 0)) / 1_000_000, 6)


class LLMClient:
    def __init__(self, role: LLMRole, db: Database, ledger: Ledger, prices: dict,
                 stage: str, prompt_version: str = "v1", replay: bool = False,
                 governor: Any = None):
        if not role.model:
            raise ValueError(f"LLM role '{stage}': model chưa cấu hình (env/YAML)")
        self.role, self.db, self.ledger, self.prices = role, db, ledger, prices
        self.stage, self.prompt_version = stage, prompt_version
        self.replay = replay  # offline = cache-only, KHÔNG gọi mạng khi cache miss
        self.governor = governor
        self.chain = [role] + [f for f in role.fallbacks if f.model and f.api_key]
        self._clients: dict[str, Any] = {}

    def _sdk(self, role: LLMRole):
        key = f"{role.base_url}|{role.model}"
        if key not in self._clients:
            if not role.api_key:
                raise LLMUnavailable(f"thiếu API key cho model={role.model} (role {self.stage})")
            from openai import OpenAI
            self._clients[key] = OpenAI(base_url=role.base_url or None,
                                        api_key=role.api_key,
                                        timeout=role.timeout_s, max_retries=2)
        return self._clients[key]

    def judge(self, system: str, content: Any, schema: type[T], entity_id: str,
              rubric_version: str = "v1", max_attempts: int = 3,
              cache_key: str | None = None) -> T:
        """content: str or OpenAI-style content blocks (text / image_url).
        cache_key: explicit stable identity (S4 uses video file_hash+transcript hash
        so offline replay hits cache without re-rendering base64 frames)."""
        state_hash = cache_key or canonical_hash({"s": system, "c": content, "schema": schema.__name__})
        errors = []
        for i, member in enumerate(self.chain):
            row = self.db.one(
                "SELECT output_json FROM judgements WHERE model=? AND prompt_version=?"
                " AND rubric_version=? AND state_hash=?",
                (member.model, self.prompt_version, rubric_version, state_hash))
            if row:
                self.ledger.log("llm", self.stage, entity_id=entity_id, cache_hit=True,
                                note=member.model)
                return schema.model_validate_json(row["output_json"])
            if self.replay:
                # cache-only: vẫn kiểm cache của mọi member trong chain (live có thể
                # đã dùng fallback), tuyệt đối không gọi mạng
                errors.append(f"{member.model}: không có judgement cache (replay)")
                continue
            try:
                return self._judge_live(member, system, content, schema, entity_id,
                                        state_hash, rubric_version, max_attempts)
            except GovernorBlocked as e:
                errors.append(f"{member.model}: {e}")
                self.ledger.log("llm", self.stage, entity_id=entity_id,
                                note=f"GOVERNOR_BLOCKED {member.model}: {str(e)[:200]}")
                raise
            except LLMUnavailable as e:
                errors.append(f"{member.model}: {e}")
                self.ledger.log("llm", self.stage, entity_id=entity_id,
                                note=f"UNAVAILABLE {member.model}: {str(e)[:200]}"
                                     + (f" → fallback {self.chain[i + 1].model}" if i + 1 < len(self.chain) else " (hết chain)"))
        if self.replay:
            # Offline replay fallback: người chấm chạy không có .env (model mặc định
            # trong defaults.yaml khác prefix proxy 'ag/' trong judgements_bundle.json)
            # → khớp theo (prompt_version, rubric_version, state_hash) bất kể tên model.
            row = self.db.one(
                "SELECT output_json, model FROM judgements WHERE prompt_version=?"
                " AND rubric_version=? AND state_hash=? ORDER BY created_at DESC, rowid DESC LIMIT 1",
                (self.prompt_version, rubric_version, state_hash))
            if not row and self.stage == "s4" and state_hash.count(":") >= 4:
                # Fresh git clone không có thư mục runs/*/transcripts/ (gitignored) →
                # thash ở đoạn cuối state_hash khác chuỗi rỗng; vẫn khóa chặt theo
                # (stage, entity_id, prompt_version, rubric_version, file_hash).
                prefix = ":".join(state_hash.split(":")[:4]) + ":%"
                row = self.db.one(
                    "SELECT output_json, model FROM judgements WHERE stage=? AND entity_id=?"
                    " AND prompt_version=? AND rubric_version=? AND state_hash LIKE ?"
                    " ORDER BY created_at DESC, rowid DESC LIMIT 1",
                    (self.stage, entity_id, self.prompt_version, rubric_version, prefix))
            if row:
                self.ledger.log("llm", self.stage, entity_id=entity_id, cache_hit=True,
                                note=f"replay:{row['model']}")
                return schema.model_validate_json(row["output_json"])
        raise LLMUnavailable(" | ".join(errors))

    def _judge_live(self, role: LLMRole, system: str, content: Any, schema: type[T],
                    entity_id: str, state_hash: str, rubric_version: str,
                    max_attempts: int) -> T:
        messages: list[dict] = [{"role": "system", "content": system},
                                {"role": "user", "content": content}]
        use_json_object = False
        use_max_tokens = False
        last_err = ""
        for attempt in range(1, max_attempts + 1):
            sys_text = system
            if use_json_object:
                sys_text += ("\n\nReturn ONLY a JSON object matching this schema "
                             f"(no markdown, no extra keys):\n{json.dumps(_strict_schema(schema), ensure_ascii=False)}")
            if last_err:
                sys_text += f"\n\nPrevious attempt was invalid: {last_err}. Fix it."
            msgs = [{"role": "system", "content": sys_text}, messages[1]]
            rf: dict = ({"type": "json_object"} if use_json_object else
                        {"type": "json_schema",
                         "json_schema": {"name": schema.__name__, "strict": True,
                                         "schema": _strict_schema(schema)}})
            kw: dict = dict(model=role.model, messages=msgs, response_format=rf)
            if use_max_tokens:
                kw["max_tokens"] = role.max_tokens
            else:
                kw["max_completion_tokens"] = role.max_tokens
            if role.extra:
                kw["extra_body"] = role.extra
            if self.governor is not None:
                ok, gmsg = self.governor.check_llm_call(self.stage, entity_id)
                if not ok:
                    raise GovernorBlocked(gmsg)
            t0 = time.perf_counter()
            try:
                resp = self._sdk(role).chat.completions.create(**kw)
            except LLMUnavailable:
                raise
            except Exception as e:
                from openai import BadRequestError
                text = str(e).lower()
                if isinstance(e, BadRequestError) and not use_json_object and (
                        "response_format" in text or "json_schema" in text or "strict" in text):
                    use_json_object = True
                    continue
                if isinstance(e, BadRequestError) and not use_max_tokens and "max_completion_tokens" in text:
                    use_max_tokens = True
                    continue
                # auth/quota/model-not-found/transient-after-SDK-retries/schema-400:
                # không retry mù cùng provider — chuyển chain, ghi ledger
                raise LLMUnavailable(f"{type(e).__name__}: {str(e)[:300]}") from e
            latency = int((time.perf_counter() - t0) * 1000)
            usage = getattr(resp, "usage", None)
            tin = getattr(usage, "prompt_tokens", 0) or 0
            tout = getattr(usage, "completion_tokens", 0) or 0
            details = getattr(usage, "prompt_tokens_details", None)
            tcached = getattr(details, "cached_tokens", 0) or 0
            text = resp.choices[0].message.content or ""
            try:
                obj = schema.model_validate_json(text)
            except (ValidationError, ValueError) as e:
                last_err = str(e)[:500]
                self.ledger.log("llm", self.stage, entity_id=entity_id, tokens_in=tin,
                                tokens_out=tout, tokens_cached=tcached,
                                cost_usd=_cost(self.prices, role.model, tin, tout, tcached),
                                latency_ms=latency, note=f"{role.model} invalid_attempt={attempt}")
                continue
            out = obj.model_dump_json()
            jid = "j_" + state_hash[:16]
            with self.db.transaction() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO judgements (judgement_id, run_id, stage, entity_id,"
                    " model, prompt_version, rubric_version, state_hash, output_json, attempts)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (jid, self.ledger.run_id, self.stage, entity_id, role.model,
                     self.prompt_version, rubric_version, state_hash, out, attempt))
            self.ledger.log("llm", self.stage, entity_id=entity_id, tokens_in=tin,
                            tokens_out=tout, tokens_cached=tcached,
                            cost_usd=_cost(self.prices, role.model, tin, tout, tcached),
                            latency_ms=latency, note=role.model)
            return obj
        raise LLMUnavailable(f"schema không hợp lệ sau {max_attempts} attempt: {last_err[:200]}")
