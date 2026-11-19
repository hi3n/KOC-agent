"""Run configuration: YAML defaults + env expansion + AI brief analysis merge.

Provider-neutral by design: every LLM role resolves base_url/api_key/model from
env/YAML; no provider or model string is hardcoded in logic.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")


def expand_env(obj: Any) -> Any:
    if isinstance(obj, str):
        def sub(m: re.Match) -> str:
            return os.environ.get(m.group(1), m.group(2) if m.group(2) is not None else "")
        return _ENV_RE.sub(sub, obj)
    if isinstance(obj, dict):
        return {k: expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env(v) for v in obj]
    return obj


def canonical_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


class LLMRole(BaseModel):
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout_s: float = 180
    max_tokens: int = 4096
    extra: dict = Field(default_factory=dict)
    fallbacks: list["LLMRole"] = Field(default_factory=list)


class BriefAnalysis(BaseModel):
    """S0 output — AI phân tích brief, grounded trên cây danh mục thật."""
    product: str
    category_ids: list[str] = Field(default_factory=list)
    category_names: list[str] = Field(default_factory=list)
    niche_keywords: list[str] = Field(default_factory=list)
    audience_gender: str = "female"
    audience_age_range: str = "18-30"
    audience_region: str = "VN"
    objective: str = "conversion"          # conversion | awareness
    competitors: list[str] = Field(default_factory=list)
    budget_vnd: int = 30_000_000
    rationale: str = ""                    # AI giải thích cách hiểu brief → echo vào report


class RunConfig(BaseModel):
    raw: dict                              # defaults.yaml đã expand env + merge brief
    brief_text: str = ""
    brief_analysis: BriefAnalysis | None = None
    as_of: str = "2026-11-18"
    seed: int = 42
    run_id: str = ""

    # --- accessors ---
    def llm_role(self, name: str) -> LLMRole:
        llm = self.raw["llm"]
        merged = dict(llm["default"])
        role = llm.get("roles", {}).get(name, {})
        for k, v in role.items():
            if v not in (None, "", {}) and k != "fallbacks":
                merged[k] = v
        # chain = role.fallbacks + global llm.fallback. OPT-IN tường minh:
        # entry không khai báo model = bỏ (không kế thừa model default — smoke
        # 19/11 lộ bug: fallback rỗng tự thành bản sao provider chính, retry thừa).
        fbs = []
        for f in list(role.get("fallbacks", [])) + ([llm["fallback"]] if llm.get("fallback") else []):
            if not f.get("model"):
                continue
            fm = dict(llm["default"])
            fm.update({k: v for k, v in f.items() if v not in (None, "", {})})
            fbs.append(LLMRole(**fm))
        merged["fallbacks"] = fbs
        return LLMRole(**merged)

    @property
    def date_range(self) -> str:
        end = date.fromisoformat(self.as_of)
        days = int(self.raw["run"].get("date_range_days", 30))
        start = end - timedelta(days=days - 1)
        return f"{start.isoformat()}~{end.isoformat()}"

    @property
    def funnel(self) -> dict:
        return self.raw["funnel"]

    @property
    def kalodata(self) -> dict:
        return self.raw["kalodata"]

    def config_hash(self) -> str:
        return canonical_hash({
            "raw": self.raw, "brief": self.brief_text,
            "analysis": self.brief_analysis.model_dump() if self.brief_analysis else None,
            "as_of": self.as_of, "seed": self.seed,
        })[:16]


def load_defaults(path: str | Path = "config/defaults.yaml") -> dict:
    load_dotenv()
    with open(path, encoding="utf-8") as f:
        return expand_env(yaml.safe_load(f))


def load_prices(path: str | Path = "config/prices.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_config(defaults_path: str | Path = "config/defaults.yaml",
                 brief_text: str = "", analysis: BriefAnalysis | None = None,
                 overrides: dict | None = None) -> RunConfig:
    raw = load_defaults(defaults_path)
    if overrides:
        _deep_merge(raw, overrides)
    if analysis is not None:
        _deep_merge(raw, {
            "budget": {"total_vnd": analysis.budget_vnd},
            "campaign": {
                "objective": analysis.objective,
                "competitors": analysis.competitors,
                "category_ids": analysis.category_ids,
                "niche_keywords": analysis.niche_keywords,
                "audience": {
                    "gender": analysis.audience_gender,
                    "age_range": analysis.audience_age_range,
                    "region": analysis.audience_region,
                },
            },
        })
    cfg = RunConfig(raw=raw, brief_text=brief_text, brief_analysis=analysis,
                    as_of=str(raw["run"]["as_of"]), seed=int(raw["run"]["seed"]))
    return cfg


def _deep_merge(base: dict, extra: dict) -> None:
    for k, v in extra.items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
