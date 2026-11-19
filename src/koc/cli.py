"""CLI: run / resume / report / bench / export-bundle.

run      — full pipeline from a natural-language brief (AI parses it at S0)
resume   — re-enter a run; completed tasks skipped, zero extra cost for done work
report   — regenerate CSV/Markdown from stored state (no API/LLM calls)
bench    — warm re-run (tasks reset, caches kept) + cold/warm benchmark split
export-bundle — dump judgements+videos so graders can replay offline without keys
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer

# Windows console cp1252 vỡ tiếng Việt (smoke 19/11) — ép UTF-8 cho mọi lệnh CLI
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from .pipeline import create_ctx, run_pipeline
from . import report as report_mod

app = typer.Typer(add_completion=False, help="AI KOC Discovery — evidence-based, resumable, provider-neutral")


@app.command()
def run(brief: str = typer.Option("briefs/sunscreen.txt", help="Brief ngôn ngữ tự nhiên"),
        candidates: int = typer.Option(None, help="Override số ứng viên (demo mặc định 30)"),
        run_id: str = typer.Option(None),
        offline: bool = typer.Option(False, help="Replay từ fixtures, không gọi mạng")):
    overrides = {"funnel": {"candidates": candidates}} if candidates else None
    ctx = create_ctx(brief, mode="replay" if offline else "rw", run_id=run_id, overrides=overrides)
    print(f"run_id={ctx.cfg.run_id} mode={ctx.mode}")
    run_pipeline(ctx)
    print(f"Xong. Report: runs/{ctx.cfg.run_id}/report.md")


@app.command()
def resume(run_id: str, offline: bool = typer.Option(False)):
    ctx = create_ctx(None, mode="replay" if offline else "rw", run_id=run_id)
    stale = ctx.db.reset_stale_running(run_id)
    retryable = ctx.db.reset_retryable_failed(run_id)
    print(f"resume {run_id}: reset {stale} task stale 'running', {retryable} failed-retryable")
    run_pipeline(ctx)
    print(f"Xong. Report: runs/{run_id}/report.md")


@app.command()
def report(run_id: str):
    ctx = create_ctx(None, mode="replay", run_id=run_id)
    report_mod.write_all(ctx)
    print(f"Report: runs/{run_id}/report.md")


@app.command()
def bench(run_id: str):
    """Warm re-run: reset tasks to pending, keep caches -> every call is a hit.
    Proves resume/warm cost = 0 with the real call flow, then splits the ledger."""
    ctx = create_ctx(None, mode="rw", run_id=run_id)
    ctx.db.execute("UPDATE tasks SET status='pending' WHERE run_id=? AND stage NOT LIKE '%cut%'",
                   (run_id,))
    run_pipeline(ctx)
    report_mod.write_benchmark(ctx)
    print(f"Benchmark (cold+warm): runs/{run_id}/benchmark.md")


@app.command(name="export-bundle")
def export_bundle(run_id: str):
    ctx = create_ctx(None, mode="replay", run_id=run_id)
    js = ctx.db.query(
        "SELECT * FROM judgements WHERE run_id=? AND rowid IN"
        " (SELECT MAX(rowid) FROM judgements WHERE run_id=? GROUP BY stage, entity_id)"
        " ORDER BY stage, entity_id", (run_id, run_id))
    vs = ctx.db.query("SELECT * FROM videos WHERE run_id=? ORDER BY video_id", (run_id,))
    out = Path("fixtures") / "judgements_bundle.json"
    out.write_text(json.dumps({"judgements": js, "videos": vs}, ensure_ascii=False),
                   encoding="utf-8")
    print(f"Bundle: {out} ({len(js)} judgements, {len(vs)} videos) — commit để replay offline không cần key")


if __name__ == "__main__":
    app()
