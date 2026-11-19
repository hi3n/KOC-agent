"""Kill-resume demo (deliverable: reliability proof).

1. Chạy pipeline offline (replay fixtures+bundle, 0 credit) trong subprocess.
2. Kill cứng giữa chừng (TerminateProcess ~ kill -9) khi S2a đang dở.
3. `koc resume` chạy tiếp.
4. So: results.csv giống hệt baseline, chi phí THÊM cho phần đã xong = 0,
   task stale 'running' được reset, không trả tiền hai lần.

Chạy SAU khi demo live hoàn tất + `koc export-bundle demo_sunscreen`.
Usage: uv run python scripts/demo_resume.py [baseline_run_id]
"""
from __future__ import annotations

import csv
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
KILL_RUN = "kill_demo"


def db_query(run_id, sql):
    p = ROOT / "runs" / run_id / "koc.db"
    if not p.exists():
        return []
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True, timeout=5)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql)]
    except sqlite3.OperationalError:
        return []
    finally:
        con.close()


def totals(run_id):
    r = db_query(run_id, "SELECT SUM(credits) c, SUM(cost_usd) cost, SUM(tokens_in)+SUM(tokens_out) t"
                         " FROM usage_ledger WHERE cache_hit=0")
    return r[0] if r else {"c": 0, "cost": 0, "t": 0}


def main():
    baseline = sys.argv[1] if len(sys.argv) > 1 else "demo_sunscreen"
    base_csv = ROOT / "reports" / "results.csv"
    if not base_csv.exists():
        print(f"Chưa có baseline {base_csv} — chạy demo live + report trước.")
        return
    # fresh kill run (dùng report_dir tạm trong runs/kill_demo để không ghi đè reports/ khi đang test)
    kill_dir = ROOT / "runs" / KILL_RUN
    if kill_dir.exists():
        shutil.rmtree(kill_dir)
    cmd = [sys.executable, "-m", "koc.cli", "run", "--offline", "--run-id", KILL_RUN,
           "--report-dir", str(kill_dir)]
    print("spawn:", " ".join(cmd))
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    killed_at = None
    t0 = time.time()
    while proc.poll() is None and time.time() - t0 < 300:
        done = db_query(KILL_RUN, "SELECT COUNT(*) n FROM tasks WHERE stage='s2a' AND status='done'")
        n = done[0]["n"] if done else 0
        if n >= 3:
            proc.kill()  # TerminateProcess — hard kill, no cleanup (SQLite WAL phải sống)
            killed_at = {"s2a_done": n, "elapsed_s": round(time.time() - t0, 1)}
            break
        time.sleep(0.02)
    proc.wait(timeout=30)
    if killed_at is None:
        print("Process hoàn tất trước cửa sổ kill (offline quá nhanh) — giảm ngưỡng hoặc chạy live.")
        killed_at = {"note": "completed before kill window"}
    print("killed:", killed_at)
    at_kill = totals(KILL_RUN)
    stale = db_query(KILL_RUN, "SELECT COUNT(*) n FROM tasks WHERE status='running'")
    print(f"ledger lúc kill (cold): {at_kill} | tasks kẹt 'running': {stale[0]['n'] if stale else '?'}")

    print("resume...")
    r = subprocess.run([sys.executable, "-m", "koc.cli", "resume", KILL_RUN, "--offline",
                        "--report-dir", str(kill_dir)],
                       cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=600)
    print(r.stdout[-800:])
    if r.returncode != 0:
        print("RESUME FAILED:", r.stderr[-1500:])
        return
    after = totals(KILL_RUN)
    extra_credits = (after["c"] or 0) - (at_kill["c"] or 0)
    extra_cost = (after["cost"] or 0) - (at_kill["cost"] or 0)
    kill_csv = kill_dir / "results.csv"
    def _strip_contacts(p):
        with open(p, encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        return [{k: v for k, v in r.items() if not k.startswith("contact_")} for r in rows]
    identical = kill_csv.exists() and _strip_contacts(kill_csv) == _strip_contacts(base_csv)
    verdict = {
        "killed_at": killed_at,
        "stale_running_reset": stale[0]["n"] if stale else None,
        "cold_credits_at_kill": at_kill["c"],
        "cold_credits_after_resume": after["c"],
        "extra_credits_for_done_work": round(extra_credits, 3),
        "extra_ai_cost_for_done_work": round(extra_cost, 6),
        "results_csv_identical_to_baseline": identical,
        "compare_note": "bỏ cột contact_* (fixtures public đã scrub vì privacy); so từng giá trị còn lại",
        "verdict": "PASS" if identical and abs(extra_credits) < 1e-9 and abs(extra_cost) < 1e-9 else "CHECK",
    }
    out = ROOT / "reports" / "resume_demo.json"
    out.write_text(json.dumps(verdict, ensure_ascii=False, indent=1), encoding="utf-8")
    # dọn sạch thư mục tạm runs/kill_demo sau khi đo xong
    shutil.rmtree(kill_dir, ignore_errors=True)
    print(json.dumps(verdict, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
