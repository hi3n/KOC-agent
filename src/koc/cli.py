"""CLI: run / resume / report / bench / export-bundle.

run      — MỘT LỆNH ra tất cả: pipeline S0-S5 + report.md + CSV + benchmark.md
           + dashboard.html (tự sinh). --open để mở dashboard ngay trong browser.
resume   — chạy tiếp run dở; task xong giữ nguyên, 0đ cho phần đã xong
report   — dựng lại toàn bộ report + dashboard từ DB (không gọi API/LLM)
bench    — warm re-run (tasks reset, caches kept) + cold/warm benchmark split
export-bundle — dump judgements+videos để người chấm replay offline không cần key
"""
from __future__ import annotations

import json
import sys
import webbrowser
from pathlib import Path

import typer

# Windows console cp1252 vỡ tiếng Việt (smoke 19/11) — ép UTF-8 cho mọi lệnh CLI
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .pipeline import create_ctx, run_pipeline
from . import report as report_mod

app = typer.Typer(add_completion=False, help="AI KOC Discovery — evidence-based, resumable, provider-neutral")

_OPEN_HELP = "Mở dashboard.html trong browser ngay khi xong"


def _outputs(ctx, open_browser: bool = False):
    """In đủ bộ kết quả trong thư mục reports/ — dashboard đầu tiên cho người xem/duyệt nhanh."""
    print(f"Xong run {ctx.cfg.run_id}. Bộ kết quả ({ctx.report_dir}):")
    dash = None
    for f in ("dashboard.html", "report.md", "results.csv", "excluded.csv", "benchmark.md"):
        p = ctx.report_dir / f
        if p.exists():
            print(f"  {p}")
            if f == "dashboard.html":
                dash = p
    t = ctx.ledger.totals()
    print(f"  Chi phí tích lũy của run (ledger đo thật): {t['credits']:.1f} credit Kalodata + ${t['cost']:.2f} AI")
    if dash:
        print(f"  Mở nhanh dashboard: {dash}")
        if open_browser:
            webbrowser.open(dash.resolve().as_uri())


@app.command()
def run(brief: str = typer.Option("briefs/sunscreen.txt", help="Brief ngôn ngữ tự nhiên"),
        candidates: int = typer.Option(None, help="Override số ứng viên (demo mặc định 30)"),
        run_id: str = typer.Option(None, help="Mặc định: demo_sunscreen"),
        report_dir: str = typer.Option(None, help="Thư mục xuất báo cáo (mặc định: reports)"),
        offline: bool = typer.Option(False, help="Replay từ fixtures, không gọi mạng, không cần key"),
        open: bool = typer.Option(False, "--open", help=_OPEN_HELP)):
    overrides = {"funnel": {"candidates": candidates}} if candidates else None
    ctx = create_ctx(brief, mode="replay" if offline else "rw", run_id=run_id,
                     overrides=overrides, report_dir=report_dir)
    print(f"run_id={ctx.cfg.run_id} mode={ctx.mode} reports={ctx.report_dir}")
    run_pipeline(ctx)
    _outputs(ctx, open)


@app.command()
def resume(run_id: str = typer.Argument("demo_sunscreen"),
           report_dir: str = typer.Option(None, help="Thư mục xuất báo cáo (mặc định: reports)"),
           offline: bool = typer.Option(False),
           open: bool = typer.Option(False, "--open", help=_OPEN_HELP)):
    ctx = create_ctx(None, mode="replay" if offline else "rw", run_id=run_id, report_dir=report_dir)
    stale = ctx.db.reset_stale_running(run_id)
    retryable = ctx.db.reset_retryable_failed(run_id)
    print(f"resume {run_id}: reset {stale} task stale 'running', {retryable} failed-retryable")
    run_pipeline(ctx)
    _outputs(ctx, open)


@app.command()
def report(run_id: str = typer.Argument("demo_sunscreen"),
           report_dir: str = typer.Option(None, help="Thư mục xuất báo cáo (mặc định: reports)"),
           open: bool = typer.Option(False, "--open", help=_OPEN_HELP)):
    ctx = create_ctx(None, mode="replay", run_id=run_id, report_dir=report_dir)
    report_mod.write_all(ctx)
    _outputs(ctx, open)


@app.command()
def bench(run_id: str = typer.Argument("demo_sunscreen"),
          report_dir: str = typer.Option(None, help="Thư mục xuất báo cáo (mặc định: reports)")):
    """Warm re-run: reset tasks to pending, keep caches -> every call is a hit.
    Proves resume/warm cost = 0 with the real call flow, then splits the ledger."""
    ctx = create_ctx(None, mode="rw", run_id=run_id, report_dir=report_dir)
    ctx.db.execute("UPDATE tasks SET status='pending' WHERE run_id=? AND stage NOT LIKE '%cut%'",
                   (run_id,))
    run_pipeline(ctx)
    report_mod.write_benchmark(ctx)
    _outputs(ctx)


@app.command(name="export-bundle")
def export_bundle(run_id: str = typer.Argument("demo_sunscreen")):
    from .db import Database
    db = Database(Path("runs") / run_id / "koc.db")
    js = db.query(
        "SELECT * FROM judgements WHERE run_id=? AND rowid IN"
        " (SELECT MAX(rowid) FROM judgements WHERE run_id=? GROUP BY stage, entity_id)"
        " ORDER BY stage, entity_id", (run_id, run_id))
    vs = db.query("SELECT * FROM videos WHERE run_id=? ORDER BY video_id", (run_id,))
    db.close()
    out = Path("fixtures") / "judgements_bundle.json"
    out.write_text(json.dumps({"judgements": js, "videos": vs}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"Bundle: {out} ({len(js)} judgements, {len(vs)} videos) — commit để replay offline không cần key")


if __name__ == "__main__":
    app()
