"""Orchestrator context + re-entrant pipeline.

Every stage reads its inputs from the DB (tasks.result_json / cache), never from
in-memory state of a previous stage -> `resume` re-enters the same orchestration
and completed items are skipped. Config snapshot lives in runs.config_json.
"""
from __future__ import annotations

import json
import os
import time
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
        self.last_elapsed_s: float = 0.0
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


def fmt_elapsed(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{int(m)}m {s:.1f}s"
    h, m = divmod(int(m), 60)
    return f"{h}h {m:02d}m {int(round(s)):02d}s"


def _fmt_clock(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"[{h:02d}:{m:02d}:{s:02d}]" if h else f"[{m:02d}:{s:02d}]"


def run_pipeline(ctx: Ctx, progress: bool = False):
    from .stages import s0_brief, s1_candidates, s2_metrics, s3_screen, s4_video, s5_select
    from . import report

    t_start = time.perf_counter()
    steps = [
        ("S0 phân tích brief", "Đang phân tích brief & khớp danh mục Kalodata...", lambda: s0_brief.run(ctx)),
        ("S1 tìm ứng viên", "Đang lấy danh sách KOC từ các lát cắt Kalodata...", lambda: s1_candidates.run(ctx)),
        ("S2 chấm số liệu & lọc thô", "Đang tải stats video + detail từng KOC & tính điểm số liệu...", lambda: s2_metrics.run(ctx)),
        ("S3 sàng lọc ngữ nghĩa", "Đang chấm ngữ nghĩa & đối thủ qua LLM theo batch...", lambda: s3_screen.run(ctx)),
        ("S4 phân tích video đa phương thức", "Đang tải MP4, trích frames, bóc băng ASR & chấm video (bước lâu nhất, vui lòng chờ)...", lambda: s4_video.run(ctx)),
        ("S5 chọn bộ & viết lý do", "Đang tối ưu tổ hợp trong ngân sách & tổng hợp lý do có bằng chứng...", lambda: s5_select.run(ctx)),
        ("Xuất báo cáo & Dashboard", "Đang dựng dashboard.html, report.md, CSV & benchmark.md...", lambda: report.write_all(ctx)),
    ]
    if progress:
        print(f"[00:00] Bắt đầu chạy KOC Discovery (run_id={ctx.cfg.run_id}, mode={ctx.mode}, reports={ctx.report_dir})", flush=True)
        print(f"        Vui lòng chờ — đang xử lý tuần tự {len(steps)} bước (S0 -> S5 + xuất báo cáo)...", flush=True)

        def _on_prog(stage: str, done: int, total: int, status: str):
            clk = _fmt_clock(time.perf_counter() - t_start)
            print(f"{clk}   ... {stage}: {done}/{total} xong", flush=True)

        ctx.runner.on_progress = _on_prog

    try:
        for idx, (label, desc, fn) in enumerate(steps, 1):
            if progress:
                clk = _fmt_clock(time.perf_counter() - t_start)
                print(f"{clk} [{idx}/{len(steps)}] {label}: {desc}", flush=True)
            t_step = time.perf_counter()
            fn()
            if progress:
                dt = time.perf_counter() - t_step
                clk = _fmt_clock(time.perf_counter() - t_start)
                print(f"{clk} [OK] {label} xong ({fmt_elapsed(dt)})", flush=True)
    finally:
        if progress:
            ctx.runner.on_progress = None

    ctx.db.execute("UPDATE runs SET status='done', finished_at=datetime('now') WHERE run_id=?",
                   (ctx.cfg.run_id,))
    ctx.last_elapsed_s = time.perf_counter() - t_start
    return ctx
