"""Orchestrator context + re-entrant pipeline.

Every stage reads its inputs from the DB (tasks.result_json / cache), never from
in-memory state of a previous stage -> `resume` re-enters the same orchestration
and completed items are skipped. Config snapshot lives in runs.config_json.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .config import BriefAnalysis, RunConfig, build_config, load_prices
from .db import Database
from .governor import Governor
from .kalodata import KalodataClient
from .ledger import Ledger
from .llm import LLMClient
from .runner import StageRunner


class Ctx:
    def __init__(self, cfg: RunConfig, db: Database, ledger: Ledger,
                 kd: KalodataClient, mode: str = "rw",
                 run_dir: str | Path | None = None,
                 report_dir: str | Path | None = None):
        self.cfg, self.db, self.ledger, self.kd = cfg, db, ledger, kd
        self.mode = mode
        self.runner = StageRunner(db, ledger, cfg.run_id)
        self.governor = Governor(db, ledger, cfg.run_id, cfg.raw.get("limits", {}))
        self.kd.governor = self.governor
        self.prices = load_prices()
        self.run_dir = Path(run_dir) if run_dir else (Path("runs") / cfg.run_id)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.report_dir = Path(report_dir) if report_dir else Path("reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self._llm: dict[str, LLMClient] = {}

    def llm(self, role: str, stage: str) -> LLMClient:
        if role not in self._llm:
            self._llm[role] = LLMClient(self.cfg.llm_role(role), self.db, self.ledger,
                                        self.prices, stage, replay=(self.mode == "replay"),
                                        governor=self.governor)
        return self._llm[role]

    @property
    def campaign(self) -> dict:
        return self.cfg.raw.get("campaign", {})

    def stage_result(self, stage: str, entity: str = "pool") -> dict | None:
        r = self.db.one("SELECT result_json FROM tasks WHERE run_id=? AND stage=? AND entity_id=?",
                        (self.cfg.run_id, stage, entity))
        return json.loads(r["result_json"]) if r and r["result_json"] else None

    def put_stage_result(self, stage: str, result: dict, entity: str = "pool"):
        self.db.execute(
            "INSERT INTO tasks (run_id, stage, entity_id, status, result_json, updated_at)"
            " VALUES (?,?,?,'done',?,datetime('now'))"
            " ON CONFLICT(run_id, stage, entity_id) DO UPDATE SET result_json=excluded.result_json,"
            " status='done', updated_at=datetime('now')",
            (self.cfg.run_id, stage, entity, json.dumps(result, ensure_ascii=False, default=str)))


def create_ctx(brief_path: str | Path | None = None, mode: str = "rw",
               run_id: str | None = None, overrides: dict | None = None,
               db_path: str | Path | None = None,
               report_dir: str | Path | None = None) -> Ctx:
    brief_text = Path(brief_path).read_text(encoding="utf-8") if brief_path else ""
    cfg = build_config(brief_text=brief_text, overrides=overrides)
    cfg.run_id = run_id or "demo_sunscreen"
    db = Database(db_path or Path("runs") / cfg.run_id / "koc.db")
    row = db.one("SELECT config_json FROM runs WHERE run_id=?", (cfg.run_id,))
    if row:
        # Resume: snapshot giữ IDENTITY của thí nghiệm (campaign đã phân tích, funnel
        # widths, as_of, seed -> khóa cache bất biến). Infra knobs (rate limit,
        # concurrency, budget cap, models) lấy defaults HIỆN TẠI để vận hành sửa được
        # giữa chừng mà không phá cache. Đổi model = khoá judgement mới (ghi ledger).
        snap = json.loads(row["config_json"])
        from .config import load_defaults, _deep_merge
        fresh = load_defaults()
        if snap["raw"].get("campaign"):
            fresh["campaign"] = snap["raw"]["campaign"]
        # funnel: giữ trường ảnh hưởng KHÓA CACHE API (candidates/slices/page_size/
        # videos_fetch); knobs cắt giảm (after_2a/after_3/video_roles...) lấy defaults
        # hiện tại để chỉnh được giữa chừng mà không phá cache hay vượt credit.
        sf = snap["raw"].get("funnel", {})
        for k in ("candidates", "slices", "page_size", "videos_fetch"):
            if k in sf:
                fresh["funnel"][k] = sf[k]
        if snap["raw"].get("budget", {}).get("total_vnd"):
            fresh["budget"]["total_vnd"] = snap["raw"]["budget"]["total_vnd"]
        if overrides:
            _deep_merge(fresh, overrides)
        cfg = RunConfig(raw=fresh, brief_text=snap.get("brief_text", brief_text),
                        brief_analysis=BriefAnalysis(**snap["brief_analysis"]) if snap.get("brief_analysis") else None,
                        as_of=snap["as_of"], seed=snap["seed"], run_id=cfg.run_id)
    else:
        db.execute("INSERT INTO runs (run_id, config_json, config_hash) VALUES (?,?,?)",
                   (cfg.run_id, json.dumps({"raw": cfg.raw, "brief_text": brief_text,
                                            "brief_analysis": None, "as_of": cfg.as_of,
                                            "seed": cfg.seed}, ensure_ascii=False),
                    cfg.config_hash()))
    ledger = Ledger(db, cfg.run_id)
    kd = KalodataClient(db, ledger, cfg.kalodata, os.environ.get("KALO_API_KEY", ""),
                        mode=mode, fixtures_dir="fixtures", date_range=cfg.date_range)
    rdir = Path(db_path).parent if db_path else None
    return Ctx(cfg, db, ledger, kd, mode, run_dir=rdir, report_dir=report_dir or rdir)


def save_brief_analysis(ctx: Ctx, analysis: BriefAnalysis):
    ctx.cfg.brief_analysis = analysis
    from .config import _deep_merge
    _deep_merge(ctx.cfg.raw, {
        "budget": {"total_vnd": analysis.budget_vnd},
        "campaign": {"objective": analysis.objective, "competitors": analysis.competitors,
                     "category_ids": analysis.category_ids, "niche_keywords": analysis.niche_keywords,
                     "audience": {"gender": analysis.audience_gender,
                                  "age_range": analysis.audience_age_range,
                                  "region": analysis.audience_region}},
    })
    ctx.db.execute("UPDATE runs SET config_json=? WHERE run_id=?",
                   (json.dumps({"raw": ctx.cfg.raw, "brief_text": ctx.cfg.brief_text,
                                "brief_analysis": analysis.model_dump(),
                                "as_of": ctx.cfg.as_of, "seed": ctx.cfg.seed},
                               ensure_ascii=False), ctx.cfg.run_id))


def run_pipeline(ctx: Ctx):
    from .stages import s0_brief, s1_candidates, s2_metrics, s3_screen, s4_video, s5_select
    from . import report
    s0_brief.run(ctx)
    s1_candidates.run(ctx)
    s2_metrics.run(ctx)
    s3_screen.run(ctx)
    s4_video.run(ctx)
    s5_select.run(ctx)
    report.write_all(ctx)
    ctx.db.execute("UPDATE runs SET status='done', finished_at=datetime('now') WHERE run_id=?",
                   (ctx.cfg.run_id,))
    return ctx
