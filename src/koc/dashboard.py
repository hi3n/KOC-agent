"""Dashboard HTML cho người kinh doanh — TỰ SINH mỗi lần run/resume/report.

Port từ bản thiết kế đã duyệt 19/11 (reports/ket-qua-test-2026-11-19/dashboard.html):
cùng token màu (palette tham chiếu đã validate), cùng layout, ngôn ngữ phi kỹ thuật.
Mọi số lấy từ stage results + ledger của run hiện tại — không hardcode data demo.
Không chứa contact cá nhân (email/zalo) — chỉ tiktok handle công khai.
"""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

from .evidence import audit_numeric_claims, for_creator
from .scoring import ScoreCard

USD_VND = 25400      # tỷ giá tham khảo, ghi rõ trên trang
CREDIT_USD = 0.1     # quy đổi tham khảo, khớp benchmark

FLAG_LABELS = {
    "low_er": "Tương tác dưới ngưỡng 0,5%",
    "cold_channel": "View thấp so với follower",
    "ad_saturated": "Quảng cáo dày đặc",
    "competitor_recent": "Từng nhắc đối thủ",
    "follower_spike": "Follower tăng đột biến",
    "er_anomaly": "Số liệu tương tác bất thường",
    "er_unusually_high": "Tương tác cao bất thường",
    "knowledge_issue": "Lỗ hổng kiến thức chống nắng",
    "exaggerated_claims": "Claim phóng đại",
    "ad_no_disclosure": "Thiếu nhãn quảng cáo",
    "brand_risk": "Rủi ro thương hiệu",
    "low_confidence": "Đánh giá AI độ tin cậy thấp",
    "screen_missing": "Chưa sàng lọc nội dung",
}
ROLE_SHORT = {"anchor": "Chủ lực", "mid": "Tầm trung", "micro": "Thử nghiệm", "nano": "Nano thử nghiệm"}

# Icon SVG (không dùng text glyph trong badge — tránh chữ sát viền, đúng chuẩn icon)
SVG_OK = ('<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
          '<path d="M2 6.2 4.8 9 10 3.2" fill="none" stroke="#fff" stroke-width="2" '
          'stroke-linecap="round" stroke-linejoin="round"/></svg>')
SVG_NA = ('<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">'
          '<rect x="2" y="5.25" width="8" height="1.5" rx=".75" fill="currentColor"/></svg>')
SVG_WARN = ('<svg width="8" height="8" viewBox="0 0 8 8" aria-hidden="true">'
            '<rect x="3.25" y=".8" width="1.5" height="4.2" rx=".75" fill="#0b0b0b"/>'
            '<circle cx="4" cy="6.6" r=".95" fill="#0b0b0b"/></svg>')


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _vn(v, nd=0) -> str:
    """Định dạng số kiểu Việt Nam: 1.234.567,89"""
    try:
        x = float(v)
    except (TypeError, ValueError):
        return str(v)
    s = f"{x:,.{nd}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _ev_text(kind: str, p: dict) -> str:
    if kind == "transcript_quote":
        return f"[{_vn(p.get('start_s', 0), 1)}s] “{p.get('quote', '')[:160]}”"
    if kind == "frame_obs":
        return "; ".join(p.get("observations", []))[:160]
    if kind == "metric":
        if "median_views" in p:
            return (f"View trung vị {_vn(p['median_views'])}, tương tác {_vn(p.get('median_er', 0), 4)}, "
                    f"{p.get('n_videos', '?')} video mẫu")
        if "visual_quality" in p:
            return (f"Điểm hình ảnh (AI chấm): ánh sáng {_vn(p['visual_quality'], 2)}, "
                    f"demo {_vn(p['demo_quality'], 2)}, mở đầu {_vn(p['hook_strength'], 2)}")
        if "video_gpm" in p:
            return f"GPM video {_vn(p.get('video_gpm', 0))}, follower mới/kỳ {_vn(p.get('new_follower_ratio', 0), 3)}"
    if kind == "niche_signal":
        if "niche_fit" in p:
            return f"AI đánh giá nội dung: đúng ngách {_vn(p['niche_fit'], 2)}, uy tín {_vn(p.get('trust_signal', 0), 2)}"
        if "niche_keyword_ratio" in p:
            return f"Tỷ lệ video đúng từ khóa ngách: {_vn(p['niche_keyword_ratio'] * 100)}%"
    return ""


def collect(ctx) -> dict:
    """Gom data hiển thị từ DB của run — cùng nguồn với report.md/benchmark.md."""
    cfg = ctx.cfg
    db = ctx.db
    rid = cfg.run_id

    def stage(s):
        r = ctx.stage_result(s)
        return r if r is not None else {}

    s1, s2, s3, s4, s5 = (stage(x) for x in ("s1", "s2", "s3", "s4", "s5"))
    a = cfg.brief_analysis
    camp = ctx.campaign
    sel = s5.get("selection", {})
    portfolios = sel.get("portfolios", [])
    sel_idx = int(sel.get("selected_index", 0)) if portfolios else 0
    if not (0 <= sel_idx < len(portfolios)):
        sel_idx = 0
    p0 = portfolios[sel_idx] if portfolios else {}
    members = p0.get("members", [])
    chosen_ids = {m["creator_id"] for m in members}
    backups = [b for b in sel.get("backups", []) if b["creator_id"] not in chosen_ids]
    details = s2.get("details", {})
    reasons = {r["creator_id"]: r for r in s5.get("reasons", [])}
    cards = {k: ScoreCard(**v) for k, v in s4.get("cards", s3.get("cards", {})).items()}
    res_a = ctx.runner.done_results("s2a")
    seen = {r["creator_id"]: r["n"] for r in db.query(
        "SELECT creator_id, COUNT(*) n FROM videos WHERE run_id=? AND status='processed' GROUP BY creator_id", (rid,))}
    ev_map = {}
    for m in members + backups:
        cid = m["creator_id"]
        ev_map[cid] = {e["evidence_id"]: (e["kind"], e["payload"]) for e in for_creator(db, rid, cid)}

    exc = s2.get("excluded", [])
    exc_er = sum(1 for e in exc if e["hard"] and "ER" in e["reason"])
    exc_cap = sum(1 for e in exc if e["hard"] and "trần" in e["reason"])
    exc_other = sum(1 for e in exc if e["hard"] and "ER" not in e["reason"] and "trần" not in e["reason"])
    exc_cut2 = sum(1 for e in exc if not e["hard"])
    exc_cut3 = len(s3.get("excluded_cut", []))

    koc = []
    for i, m in enumerate(members + backups):
        cid = m["creator_id"]
        is_bk = i >= len(members)
        c = cards.get(cid)
        d = details.get(cid, {})
        r = reasons.get(cid, {})
        met = res_a.get(cid, {}).get("metrics", {})
        flags = [FLAG_LABELS.get(f["flag"], f["flag"]) for f in (c.flags if c else [])]
        strengths = []
        for s in r.get("strengths", []):
            evs = [_ev_text(*ev_map[cid][eid]) for eid in s.get("evidence_ids", [])
                   if eid in ev_map[cid] and _ev_text(*ev_map[cid][eid])]
            strengths.append({"claim": s.get("claim", ""), "ev": evs})
        koc.append({
            "n": i + 1, "name": m.get("name", d.get("name", cid)),
            "handle": str(d.get("handle", "")).lstrip("@"), "backup": is_bk,
            "role": ("Dự phòng" if is_bk else ROLE_SHORT.get(m.get("tier", ""), m.get("tier", ""))),
            "followers": m.get("followers", d.get("followers", 0)),
            "median_views": met.get("median_views", 0),
            "seen": r.get("videos_watched", {}).get("seen", seen.get(cid, 0)),
            "total_videos": r.get("videos_watched", {}).get("total", res_a.get(cid, {}).get("n_total", 0)),
            "ppw": met.get("posts_per_week", 0),
            "perf": c.performance if c else 0, "content": c.content if c else 0,
            "visual": c.visual if c else 0,
            "measured": c.measured if c else 0, "measured_max": c.measured_max if c else 65,
            "price": m.get("price_vnd", 0),
            "ceiling": p0.get("price_ceiling_vnd", {}).get(cid),
            "summary": r.get("summary", ""), "flags": flags,
            "strengths": strengths, "concerns": r.get("concerns", []),
            "verify": r.get("verify_before_contract", []),
            "issues": s5.get("validation", {}).get(cid, []),
        })

    # sensitivity rows
    sens = []
    base_ids = [m["creator_id"] for m in members]
    for s in s5.get("sensitivity", []):
        cheapest = None
        if not s["feasible"]:
            m = re.search(r"rẻ nhất có thể:\s*([\d.,]+)", s.get("infeasible_reason") or "")
            if m:
                # _fmt_money kiểu Anh "33,350,000" — strip mọi separator, số nguyên VNĐ
                cheapest = float(re.sub(r"[.,]", "", m.group(1))) / 1e6
        note = (", ".join(details.get(c, {}).get("name", c) for c in s.get("best_members", []))
                if s["feasible"] else (s.get("infeasible_reason") or "vô nghiệm"))
        sens.append({"scale": s["price_scale"], "feasible": s["feasible"],
                     "total": s.get("best_total_vnd"), "note": note, "cheapest": cheapest,
                     "same_set": s.get("best_members") == base_ids})

    alts = [{"label": f"PA{i}", "names": ", ".join(m["name"] for m in p["members"]),
             "delta": p["total_score"] - p0["total_score"], "price": p["total_price_vnd"]}
            for i, p in enumerate(portfolios, 1) if i - 1 != sel_idx]
    swaps = []
    for cid, sw in (p0.get("swap_options") or {}).items():
        nm = details.get(cid, {}).get("name", cid)
        swaps.append(f"{nm} → {sw['name']} (điểm {sw['score_delta']:+.4f})" if sw
                     else f"{nm} → không có phương án tốt hơn")

    # costs
    cold = db.query("SELECT provider, SUM(credits) credits, SUM(tokens_in) tin, SUM(tokens_out) tout,"
                    " SUM(cost_usd) cost, SUM(latency_ms) ms FROM usage_ledger"
                    " WHERE run_id=? AND cache_hit=0 GROUP BY provider", (rid,))
    cp = {r["provider"]: r for r in cold}
    credits = (cp.get("kalodata", {}).get("credits") or 0)
    ai_usd = (cp.get("llm", {}).get("cost") or 0)
    total_usd = credits * CREDIT_USD + ai_usd
    total_vnd = round(total_usd * USD_VND / 1000) * 1000
    budget_vnd = float(cfg.raw["budget"]["total_vnd"])
    warm = db.one("SELECT SUM(credits) c, SUM(cost_usd) cost FROM usage_ledger WHERE run_id=? AND cache_hit=1", (rid,)) or {}
    task_min = sum((r.get("ms") or 0) for r in cold) / 60000
    v = db.one("SELECT AVG(cost_usd) c, COUNT(*) n FROM usage_ledger WHERE run_id=? AND stage='s4'"
               " AND provider='llm' AND cache_hit=0", (rid,))
    naive = funnel500 = saving = None
    if v and v["n"]:
        unit = (v["c"] or 0) + 0.5 * CREDIT_USD
        naive = 500 * 5 * unit + 500 * 0.2 * CREDIT_USD
        funnel500 = (500 * 0.1 + 100 * 0.1 + 75 * 0.5) * CREDIT_USD + 75 * (v["c"] or 0) + 0.1
        saving = 100 * (1 - funnel500 / naive)

    # checks
    val = s5.get("validation", {})
    val_pass = sum(1 for x in val.values() if not x)
    num = audit_numeric_claims(db, rid, s5["reasons"], details) if s5.get("reasons") else None
    recall = s3.get("audit", {})
    rd = ctx.report_dir / "resume_demo.json"
    resume = json.loads(rd.read_text(encoding="utf-8")) if rd.exists() else None

    return {
        "run_id": rid, "as_of": cfg.as_of, "period": cfg.date_range.replace("~", " – "),
        "generated": date.today().isoformat(),
        "product": (a.product if a else camp.get("product", "sản phẩm")),
        "objective": (a.objective if a else camp.get("objective", "conversion")),
        "audience": (f"{a.audience_gender} {a.audience_age_range} ({a.audience_region})" if a else ""),
        "competitors": (a.competitors if a else camp.get("competitors", [])),
        "budget_vnd": budget_vnd,
        "feasible": bool(sel.get("feasible")), "infeasible_reason": sel.get("infeasible_reason"),
        "relaxation": sel.get("relaxation_used"), "s4_events": s4.get("events", []),
        "funnel": {"pool": len(s1.get("pool", [])), "kept2": len(s2.get("kept", [])),
                   "kept3": len(s3.get("kept", [])),
                   "videos": sum(seen.values()), "selected": len(members), "backups": len(backups),
                   "exc_er": exc_er, "exc_cap": exc_cap, "exc_other": exc_other,
                   "exc_cut2": exc_cut2, "exc_cut3": exc_cut3,
                   "exc_total": len(exc) + exc_cut3},
        "koc": koc,
        "budget": {"total": p0.get("total_price_vnd"), "max_scale": p0.get("max_price_scale"),
                   "tiers": cfg.raw["budget"]["price_tiers_vnd"],
                   "sens": sens, "alts": alts, "swaps": swaps,
                   "ceilings": [{"name": m.get("name", ""), "ceiling": p0.get("price_ceiling_vnd", {}).get(m["creator_id"])}
                                for m in members]},
        "cost": {"credits": credits, "kalodata_usd": credits * CREDIT_USD, "ai_usd": ai_usd,
                 "total_usd": total_usd, "total_vnd": total_vnd,
                 "pct": 100 * total_vnd / budget_vnd if budget_vnd else 0,
                 "warm_zero": bool(warm) and not (warm.get("c") or 0) and not (warm.get("cost") or 0),
                 "tin": (cp.get("llm", {}).get("tin") or 0), "tout": (cp.get("llm", {}).get("tout") or 0),
                 "task_min": task_min, "naive": naive, "funnel500": funnel500, "saving": saving},
        "checks": {"val_pass": val_pass, "val_total": len(val), "num": num,
                   "recall": recall, "resume": resume},
    }


CSS = """
:root{
  --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --muted:#898781;
  --grid:#e1e0d9; --base:#c3c2b7; --ring:rgba(11,11,11,.10);
  --accent:#2a78d6; --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b; --good-ink:#006300; --crit-ink:#d03b3b;
  --f1:#86b6ef; --f2:#5598e7; --f3:#2a78d6; --f4:#1c5cab;
  --wash:rgba(42,120,214,.07); --warn-wash:rgba(250,178,25,.12);
  --font:"Be Vietnam Pro",system-ui,-apple-system,"Segoe UI",sans-serif;
  color-scheme:light;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --base:#383835; --ring:rgba(255,255,255,.10);
  --accent:#3987e5; --s1:#3987e5; --s2:#d95926; --s3:#199e70;
  --good-ink:#0ca30c; --crit-ink:#e66767; --f1:#6da7ec; --f2:#3987e5; --f3:#256abf; --f4:#184f95;
  --wash:rgba(57,135,229,.12); --warn-wash:rgba(250,178,25,.14); color-scheme:dark;
}}
:root[data-theme="dark"]{
  --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --muted:#898781;
  --grid:#2c2c2a; --base:#383835; --ring:rgba(255,255,255,.10);
  --accent:#3987e5; --s1:#3987e5; --s2:#d95926; --s3:#199e70;
  --good-ink:#0ca30c; --crit-ink:#e66767; --f1:#6da7ec; --f2:#3987e5; --f3:#256abf; --f4:#184f95;
  --wash:rgba(57,135,229,.12); --warn-wash:rgba(250,178,25,.14); color-scheme:dark;
}
*{box-sizing:border-box}
body{background:var(--page);color:var(--ink);font-family:var(--font);font-size:15px;line-height:1.6;
  padding-block:20px 48px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));margin:0}
.wrap{max-width:1060px;margin:0 auto;display:flex;flex-direction:column;gap:28px;min-width:0}
h1{font-size:clamp(22px,3.4vw,30px);font-weight:700;line-height:1.25;margin:0;text-wrap:balance}
h2{font-size:19px;font-weight:700;margin:0 0 4px;text-wrap:balance}
h3{font-size:16px;font-weight:600;margin:0}
p{margin:0}
.sub{color:var(--ink2);font-size:14px}
.muted{color:var(--ink2);font-size:12.5px}
.num{font-variant-numeric:tabular-nums}
a{color:var(--accent)}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:4px}
header.top{position:sticky;top:env(safe-area-inset-top,0px);z-index:5;background:var(--page);
  padding-block:10px;border-bottom:1px solid var(--grid);margin-inline:calc(-1*max(16px,env(safe-area-inset-left,0px)));padding-inline:max(16px,env(safe-area-inset-left,0px))}
body::before{content:"";position:fixed;inset:0 0 auto;height:env(safe-area-inset-top,0px);z-index:10;background:var(--page)}
.toprow{max-width:1060px;margin:0 auto;display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between}
.brand{font-weight:700;font-size:14px;letter-spacing:.02em}
nav.chips{display:flex;flex-wrap:wrap;gap:6px}
nav.chips a{font-size:12.5px;font-weight:500;text-decoration:none;color:var(--ink2);border:1px solid var(--grid);
  border-radius:999px;padding:8px 14px;background:var(--surface)}
nav.chips a:hover{color:var(--accent);border-color:var(--accent)}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px;display:flex;flex-direction:column;gap:2px;min-width:0}
.tile .v{font-size:24px;font-weight:700;line-height:1.2}
.tile .l{font-size:12.5px;color:var(--ink2);font-weight:500}
.tile .n{font-size:12px;color:var(--ink2)}
.tile.hero .v{color:var(--accent)}
section{display:flex;flex-direction:column;gap:12px;min-width:0}
.card{background:var(--surface);border:1px solid var(--ring);border-radius:12px;padding:18px;min-width:0}
.callout{border-radius:10px;padding:12px 14px;font-size:13.5px;background:var(--wash);border:1px solid var(--ring)}
.callout.warn{background:var(--warn-wash)}
.callout b{font-weight:600}
.funnel{display:flex;flex-direction:column;gap:12px}
.fstage{display:grid;grid-template-columns:minmax(120px,190px) 1fr;gap:10px;align-items:center}
.fstage .fl{font-size:13px;font-weight:600;text-align:right;color:var(--ink2)}
.ftrack{position:relative;height:32px;background:var(--grid);border-radius:4px;display:flex;align-items:center;overflow:hidden;min-width:0}
.ffill{position:absolute;top:0;bottom:0;left:0;border-radius:4px 0 0 4px}
.fval{position:relative;font-size:12.5px;font-weight:700;color:var(--ink);white-space:nowrap}
.fval.in{padding-left:12px;padding-right:12px;color:#0b0b0b}
.fdesc{grid-column:2;font-size:12.5px;color:var(--ink2);margin-top:0}
.exc{display:flex;flex-wrap:wrap;gap:8px}
.pill{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;font-weight:500;border-radius:999px;padding:8px 12px;border:1px solid var(--grid);background:var(--surface);color:var(--ink2)}
.pill .dot{width:8px;height:8px;border-radius:50%;flex:none}
.koc{display:flex;flex-direction:column;gap:10px}
.koc.backup{border-style:dashed}
.khead{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:baseline;justify-content:space-between}
.kname{display:flex;flex-wrap:wrap;gap:8px;align-items:baseline;min-width:0}
.kname h3{font-size:17px}
.handle{font-size:13px;color:var(--ink2);text-decoration:none}
.handle:hover{color:var(--accent)}
.role{font-size:11.5px;font-weight:600;letter-spacing:.03em;text-transform:uppercase;color:var(--accent);
  background:var(--wash);border-radius:999px;padding:8px 12px;white-space:nowrap}
.role.bk{color:var(--ink2);background:transparent;border:1px solid var(--base)}
.kstats{display:flex;flex-wrap:wrap;gap:6px 18px;font-size:13px;color:var(--ink2)}
.kstats b{color:var(--ink);font-weight:600}
.scoreline{display:flex;align-items:center;gap:10px}
.scoretrack{flex:1;height:12px;background:var(--grid);border-radius:6px;overflow:hidden;display:flex;min-width:60px}
.scoretrack i{display:block;height:100%}
.scoretrack i+i{border-left:2px solid var(--surface)}
.scoreval{font-size:13px;font-weight:700;white-space:nowrap}
.pricerow{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13.5px}
.pricerow b{font-weight:600}
details{border-top:1px solid var(--grid);padding-top:8px}
summary{cursor:pointer;font-size:13.5px;font-weight:600;color:var(--accent);list-style:none;display:flex;gap:6px;align-items:center}
summary::-webkit-details-marker{display:none}
summary::before{content:"▸";transition:transform .15s}
details[open] summary::before{transform:rotate(90deg)}
.dbody{display:flex;flex-direction:column;gap:10px;padding-top:10px}
.strength{display:flex;flex-direction:column;gap:3px}
.strength .claim{font-size:13.5px}
.ev{font-size:12.5px;color:var(--ink2);border-left:3px solid var(--base);padding:8px 12px}
.ev::before{content:"Bằng chứng: ";font-weight:600;color:var(--ink2)}
ul.tight{margin:0;padding-left:18px;display:flex;flex-direction:column;gap:4px;font-size:13.5px}
.flags{display:flex;flex-wrap:wrap;gap:6px}
.flag{display:inline-flex;align-items:center;gap:6px;font-size:11.5px;font-weight:500;border-radius:6px;
  padding:8px 12px;background:var(--warn-wash);color:var(--ink2);border:1px solid var(--ring)}
.flag .ic{width:13px;height:13px;border-radius:50%;background:var(--warn);color:#0b0b0b;font-size:10px;font-weight:700;
  display:inline-flex;align-items:center;justify-content:center;flex:none}
.chartbox{position:relative;height:320px;min-width:0}
.chartbox.tall{height:360px}
.legend{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:12.5px;color:var(--ink2)}
.legend .li{display:inline-flex;align-items:center;gap:6px}
.legend .sw{width:12px;height:12px;border-radius:3px;flex:none}
.tblwrap{overflow-x:auto;border:1px solid var(--grid);border-radius:8px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{padding:8px 12px;text-align:left;border-bottom:1px solid var(--grid);white-space:nowrap}
td.wrapok{white-space:normal;min-width:180px}
th{font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;color:var(--ink2);font-weight:600;background:var(--surface)}
tr:last-child td{border-bottom:none}
td.r,th.r{text-align:right;font-variant-numeric:tabular-nums}
.ok{color:var(--good-ink);font-weight:600}
.bad{color:var(--crit-ink);font-weight:600}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}
.check{display:flex;gap:10px;align-items:flex-start;background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px}
.check .badge{width:26px;height:26px;border-radius:50%;background:var(--good);color:#fff;font-weight:700;font-size:14px;
  display:flex;align-items:center;justify-content:center;flex:none}
.check .badge.na{background:var(--base);color:var(--ink)}
.check h3{font-size:14px;margin-bottom:2px}
.check p{font-size:12.5px;color:var(--ink2)}
footer{border-top:1px solid var(--grid);padding-top:14px;font-size:12.5px;color:var(--ink2);display:flex;flex-direction:column;gap:4px}
@media (max-width:560px){
  .fstage{grid-template-columns:1fr}.fstage .fl{text-align:left}.fdesc{grid-column:1}
  .chartbox{height:300px}.chartbox.tall{height:420px}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
"""


def _koc_card(k: dict) -> str:
    bk = k["backup"]
    flags = "".join(f'<span class="flag"><span class="ic">{SVG_WARN}</span>{_e(f)}</span>' for f in k["flags"][:4])
    if len(k["flags"]) > 4:
        flags += f'<span class="flag">+{len(k["flags"]) - 4} cờ khác trong report.md</span>'
    w = lambda v: f"{100 * float(v) / 65:.1f}%"
    strengths = "".join(
        '<div class="strength"><span class="claim">' + _e(s["claim"]) + "</span>"
        + "".join(f'<span class="ev">{_e(e)}</span>' for e in s["ev"]) + "</div>"
        for s in k["strengths"])
    concerns = "".join(f"<li>{_e(c)}</li>" for c in k["concerns"])
    verify = "".join(f"<li>{_e(v)}</li>" for v in k["verify"])
    issues = (f'<div class="callout warn">Lý do chưa pass kiểm chứng: {_e("; ".join(k["issues"]))}</div>'
              if k["issues"] else "")
    ceiling = (f'<span>Giá trần: <b>{_vn(k["ceiling"])}đ</b></span>' if k["ceiling"] is not None
               else '<span>Trần: áp theo slot thay thế</span>')
    handle = (f'<a class="handle" href="https://www.tiktok.com/@{_e(k["handle"])}" target="_blank" rel="noopener">@{_e(k["handle"])}</a>'
              if k["handle"] else "")
    title = (f'{k["name"]}' if bk else f'{k["n"]} · {k["name"]}')
    summary = _e(k["summary"]) if k["summary"] else '<i>Lý do chưa sinh (xem report.md).</i>'
    return f'''
  <div class="card koc{' backup' if bk else ''}">
    <div class="khead"><div class="kname"><h3>{_e(title)}</h3>{handle}</div><span class="role{' bk' if bk else ''}">{_e(k["role"])}</span></div>
    <div class="kstats num"><span><b>{_vn(k["followers"])}</b> follower</span><span>View trung vị <b>{_vn(k["median_views"])}</b></span><span>Đã xem <b>{k["seen"]}/{k["total_videos"]}</b> video</span><span>Đăng <b>{_vn(k["ppw"], 1)}</b> bài/tuần</span></div>
    <div class="scoreline"><div class="scoretrack"><i style="width:{w(k["perf"])};background:var(--s1)"></i><i style="width:{w(k["content"])};background:var(--s2)"></i><i style="width:{w(k["visual"])};background:var(--s3)"></i></div><span class="scoreval num">{_vn(k["measured"], 2)} / {_vn(k["measured_max"], 0)} điểm đã đo</span></div>
    <div class="pricerow num"><span>Giá giả định: <b>{_vn(k["price"])}đ</b></span>{ceiling}</div>
    <p class="sub">{summary}</p>
    {issues}
    <div class="flags">{flags}</div>
    <details><summary>Lý do đề xuất &amp; bằng chứng</summary><div class="dbody">{strengths or '<span class="muted">Chưa có lý do dạng bằng chứng.</span>'}</div></details>
    <details><summary>Lưu ý &amp; việc cần xác minh trước khi chốt</summary><div class="dbody"><ul class="tight">{concerns}{verify}</ul></div></details>
  </div>'''


def _page(d: dict) -> str:
    f = d["funnel"]
    b = d["budget"]
    c = d["cost"]
    ck = d["checks"]
    pool = max(f["pool"], 1)
    pct = lambda n: f"{100 * n / pool:.1f}%"
    stages = [
        ("1 · Tìm ứng viên", f["pool"], "kênh", "var(--f1)", True,
         "Quét bảng xếp hạng theo nhiều góc: doanh thu, lượt xem, tăng trưởng, kênh nhỏ tiềm năng. Chỉ lấy kênh độc lập — không lấy kênh của chính hãng bán hàng."),
        ("2 · Chấm số liệu", f["kept2"], "kênh", "var(--f2)", False,
         "Tính tương tác, lượt xem trung vị, độ đều, tần suất đăng từ tối đa 100 video/kênh. Loại có lý do từng kênh."),
        ("3 · Đọc nội dung", f["kept3"], "kênh", "var(--f3)", False,
         "AI đọc tiểu sử + tiêu đề video: có đúng ngách, có nhắc đối thủ, dấu hiệu uy tín hay quảng cáo dày đặc."),
        ("4 · Xem video", f["kept3"], f'kênh · {f["videos"]} video', "var(--f3)", False,
         "Mỗi kênh 2 video đại diện. AI xem khung hình + nghe lời nói (chép thành chữ kèm mốc thời gian), chấm: ánh sáng, demo thoa thật, 3 giây đầu, kiến thức ngành."),
        ("5 · Chọn bộ tối ưu", f["selected"], f'+ {f["backups"]} dự phòng', "var(--f4)", False,
         "Duyệt mọi tổ hợp 5 người. Ràng buộc cứng: tổng giá trong ngân sách, đủ vai trò kênh, không trùng phong cách. Chọn phương án điểm cao nhất."),
    ]
    funnel_html = ""
    for label, n, unit, color, inside, desc in stages:
        w = pct(n)
        val = f"{n} {unit}"
        span = (f'<span class="fval in num">{_e(val)}</span>' if inside
                else f'<span class="fval num" style="margin-left:calc({w} + 12px)">{_e(val)}</span>')
        funnel_html += (f'<div class="fstage"><span class="fl">{_e(label)}</span>'
                        f'<div class="ftrack"><div class="ffill" style="width:{w};background:{color}"></div>{span}</div>'
                        f'<span class="fdesc">{_e(desc)}</span></div>')

    exc_pills = ""
    for n, txt, col in ((f["exc_er"], "tương tác dưới ngưỡng 0,5%", "var(--crit)"),
                        (f["exc_cap"], "vượt tầm ngân sách (quá lớn)", "var(--warn)"),
                        (f["exc_other"] + f["exc_cut2"], "điểm thấp hơn ngưỡng giữ", "var(--base)"),
                        (f["exc_cut3"], "loại ở vòng đọc nội dung", "var(--base)")):
        if n:
            exc_pills += f'<span class="pill"><span class="dot" style="background:{col}"></span>{n} kênh: {_e(txt)}</span>'

    members = [k for k in d["koc"] if not k["backup"]]
    backups = [k for k in d["koc"] if k["backup"]]
    cards_html = "".join(_koc_card(k) for k in members)
    backup_html = ('<h2 style="margin-top:8px">2 dự phòng</h2><div class="grid2">'
                   + "".join(_koc_card(k) for k in backups) + "</div>") if backups else ""
    if not d["feasible"]:
        cards_html = f'<div class="callout warn"><b>Chưa chọn được bộ KOC khả thi:</b> {_e(d["infeasible_reason"] or "xem report.md")}</div>'
        backup_html = ""

    score_rows = "".join(
        f'<tr><td>{_e(k["name"])}{" (dự phòng)" if k["backup"] else ""}</td>'
        f'<td class="r">{_vn(k["perf"], 2)}</td><td class="r">{_vn(k["content"], 2)}</td>'
        f'<td class="r">{_vn(k["visual"], 2)}</td><td class="r"><b>{_vn(k["measured"], 2)}</b></td></tr>'
        for k in sorted(d["koc"], key=lambda x: -x["measured"]))

    sens = b["sens"]
    sens_rows = ""
    for s in sens:
        lab = _vn(s["scale"], 2).rstrip("0").rstrip(",") + "×"
        if s["feasible"]:
            note = ("Giữ nguyên bộ hiện tại" if s["same_set"] else "Đổi bộ: ") + (
                f', dư {_vn(b["total"] and (d["budget_vnd"] - s["total"]) or 0)}đ' if s["same_set"] and s["total"] and s["total"] < d["budget_vnd"] else "")
            if not s["same_set"]:
                note = s["note"]
            sens_rows += (f'<tr><td>{lab}</td><td class="ok">✓</td><td class="r">{_vn(s["total"])}</td>'
                          f'<td class="wrapok">{_e(note)}</td></tr>')
        else:
            sens_rows += (f'<tr><td>{lab}</td><td class="bad">✗</td><td class="r">—</td>'
                          f'<td class="wrapok">{_e(s["note"])}</td></tr>')
    alt_rows = "".join(
        f'<tr><td>{_e(a["label"])}</td><td class="wrapok">{_e(a["names"])} (điểm {a["delta"]:+.4f})</td>'
        f'<td class="r">{_vn(a["price"])}</td></tr>' for a in b["alts"])
    ceil_rows = "".join(
        f'<tr><td>{_e(x["name"])}</td><td class="r">{_vn(x["ceiling"])}đ</td></tr>'
        for x in b["ceilings"] if x["ceiling"] is not None)
    swaps_txt = ("Hoán đổi từng người: " + "; ".join(b["swaps"]) + ".") if b["swaps"] else ""

    # checks
    res = ck["resume"]
    if res:
        ok = res.get("verdict") == "PASS"
        resume_card = (f'<div class="check"><span class="badge{"" if ok else " na"}">{SVG_OK if ok else SVG_WARN}</span><div>'
                       f'<h3>Dừng giữa chừng, chạy tiếp không mất tiền</h3>'
                       f'<p>Tắt đột ngột tiến trình khi đang xử lý rồi khởi động lại: phần đã xong không làm lại, '
                       f'chi phí thêm = {_vn(res.get("extra_credits_for_done_work", 0))} credit / '
                       f'{_vn(res.get("extra_ai_cost_for_done_work", 0))} USD, kết quả '
                       f'{"giống hệt bản chạy liền" if res.get("results_csv_identical_to_baseline") else "KHỚP MỘT PHẦN — xem resume_demo.json"}. '
                       f'Kết quả: {_e(res.get("verdict"))}.</p></div></div>')
    else:
        resume_card = (f'<div class="check"><span class="badge na">{SVG_NA}</span><div><h3>Dừng giữa chừng, chạy tiếp</h3>'
                       '<p>Chưa chạy bài test này (scripts/demo_resume.py).</p></div></div>')
    num = ck["num"]
    num_card = (f'<div class="check"><span class="badge">{SVG_OK}</span><div><h3>Con số khớp dữ liệu gốc</h3>'
                f'<p>{num["verified_total"]}/{num["total_numbers"]} con số trong lý do truy nguyên được về dữ liệu '
                f'({num["in_cited_evidence"]} số khớp ngay bằng chứng được trích tại dòng đó). '
                f'Số không khớp: {len(num["unmatched"])}.</p></div></div>') if num else \
               (f'<div class="check"><span class="badge na">{SVG_NA}</span><div><h3>Con số khớp dữ liệu gốc</h3>'
                '<p>Chưa có lý do để kiểm tra.</p></div></div>')
    rec = ck["recall"]
    rec_card = (f'<div class="check"><span class="badge">{SVG_OK}</span><div><h3>Không loại oan</h3>'
                f'<p>Chọn ngẫu nhiên {rec.get("sampled", 0)} kênh bị loại sớm, chấm lại đầy đủ bằng AI: '
                f'{rec.get("misses", 0)} kênh lẽ ra phải giữ. Danh sách {f["exc_total"]} lượt loại đều kèm lý do.</p></div></div>') \
        if rec.get("sampled") else \
        (f'<div class="check"><span class="badge na">{SVG_NA}</span><div><h3>Không loại oan</h3>'
         '<p>Chưa chạy kiểm tra mẫu loại.</p></div></div>')
    val_card = (f'<div class="check"><span class="badge">{SVG_OK}</span><div><h3>Mọi lý do đều có bằng chứng</h3>'
                f'<p>{ck["val_pass"]}/{ck["val_total"]} lý do vượt kiểm tra tự động: mỗi nhận định trích mã bằng chứng '
                f'truy được về dữ liệu gốc hoặc câu nói trong video kèm mốc thời gian. Lý do không nguồn bị loại.</p></div></div>') \
        if ck["val_total"] else \
        (f'<div class="check"><span class="badge na">{SVG_NA}</span><div><h3>Lý do có bằng chứng</h3>'
         '<p>Chưa sinh lý do.</p></div></div>')

    cost_callout = ""
    if c["naive"]:
        cost_callout = (f'<div class="callout"><b>Vì sao rẻ:</b> chỉ xem video bằng AI ở nhóm cuối '
                        f'({f["videos"]} video thay vì xem tất cả). Mở rộng lên 500 kênh: xem toàn bộ video mọi kênh tốn '
                        f'≈ {_vn(c["naive"])} USD; cách sàng lọc này ≈ {_vn(c["funnel500"])} USD — '
                        f'<b>giảm {_vn(c["saving"])}%</b> (ngoại suy từ đơn giá đo được). '
                        f'Thời gian xử lý toàn trình ≈ {_vn(c["task_min"])} phút tổng thời gian tác vụ, chạy song song nên thực tế ngắn hơn; '
                        f'chạy lại từ dữ liệu đã lưu: gần như tức thì.</div>')
    events = "".join(f'<p class="muted">Sự kiện: {_e(e)}</p>' for e in d["s4_events"])
    relaxation = (f'<div class="callout warn"><b>Nới ràng buộc có ghi nhận:</b> {_e(d["relaxation"])}</div>'
                  if d["relaxation"] else "")
    competitors = ", ".join(d["competitors"]) or "(chưa có)"
    obj_txt = "bán hàng (conversion)" if d["objective"] == "conversion" else "nhận biết (awareness)"

    chart_data = {
        "names": [k["name"] + (" (dự phòng)" if k["backup"] else "") for k in sorted(d["koc"], key=lambda x: -x["measured"])],
        "perf": [round(k["perf"], 2) for k in sorted(d["koc"], key=lambda x: -x["measured"])],
        "cont": [round(k["content"], 2) for k in sorted(d["koc"], key=lambda x: -x["measured"])],
        "vis": [round(k["visual"], 2) for k in sorted(d["koc"], key=lambda x: -x["measured"])],
        "scen": [_vn(s["scale"], 2).rstrip("0").rstrip(",") + "×" for s in sens],
        "feasible": [round(s["total"] / 1e6, 2) if s["feasible"] and s["total"] else None for s in sens],
        "cheapest": [s["cheapest"] if not s["feasible"] else None for s in sens],
        "budget": round(d["budget_vnd"] / 1e6, 2),
    }
    dj = json.dumps(chart_data, ensure_ascii=False).replace("</", "<\\/")
    has_sens = len(sens) > 1
    has_koc = bool(d["koc"])

    sens_section = f'''
<section id="ngan-sach">
  <h2>Ngân sách {_vn(d["budget_vnd"] / 1e6)} triệu: bộ nào khả thi khi giá thay đổi?</h2>
  <div class="callout warn"><b>Giá thuê là GIẢ ĐỊNH</b> (không có dữ liệu giá thật): kênh chủ lực {_vn(b["tiers"].get("anchor", 0))}đ, tầm trung {_vn(b["tiers"].get("mid", 0))}đ, kênh nhỏ {_vn(b["tiers"].get("micro", 0))}đ.
  Bộ hiện tại tổng {_vn(b["total"])}đ — hệ số giá tối đa còn khả thi: <b>{_vn(b["max_scale"], 2)}</b> ( báo giá thật cao hơn mức này phải đổi phương án). Điểm chất lượng không dùng giá.</div>
  <div class="card">
    <div class="legend">
      <span class="li"><span class="sw" style="background:var(--s1)"></span>Tổng giá bộ tối ưu (trong ngân sách)</span>
      <span class="li"><span class="sw" style="background:var(--crit)"></span>Bộ rẻ nhất có thể — vẫn vượt ngân sách</span>
      <span class="li"><span class="sw" style="background:var(--muted);height:3px;border-radius:2px"></span>Ngân sách {_vn(d["budget_vnd"] / 1e6)} triệu</span>
    </div>
    <div class="chartbox"><canvas id="sensChart" role="img" aria-label="Tổng giá bộ 5 theo các kịch bản giá, so với ngân sách"></canvas></div>
    <details><summary>Xem dạng bảng</summary><div class="dbody"><div class="tblwrap"><table class="num">
      <thead><tr><th>Mặt bằng giá</th><th>Khả thi?</th><th class="r">Tổng giá (VNĐ)</th><th class="wrapok">Bộ 5 / ghi chú</th></tr></thead>
      <tbody>{sens_rows}</tbody></table></div></div></details>
  </div>
  <div class="grid2">
    <div class="card"><h3>Phương án thay thế</h3>
      <div class="tblwrap" style="margin-top:8px"><table class="num">
        <thead><tr><th>Phương án</th><th class="wrapok">Thành viên</th><th class="r">Tổng giá</th></tr></thead>
        <tbody>{alt_rows or '<tr><td colspan="3">Không có phương án khác</td></tr>'}</tbody></table></div>
      <p class="muted" style="margin-top:8px">{_e(swaps_txt)}</p>
    </div>
    <div class="card"><h3>Giá trần từng KOC (quy tắc đàm phán)</h3>
      <div class="tblwrap" style="margin-top:8px"><table class="num">
        <thead><tr><th>KOC</th><th class="r">Giá trần</th></tr></thead>
        <tbody>{ceil_rows}</tbody></table></div>
      <p class="muted" style="margin-top:8px">Báo giá vượt trần → chuyển dự phòng cùng vai trò. Có báo giá thật thì nhập lại để chọn bộ tối ưu mới (không tốn phí phân tích lại).</p>
    </div>
  </div>
</section>''' if has_sens and d["feasible"] else ""

    score_section = f'''
<section id="diem">
  <h2>So sánh điểm đã đo giữa {len(d["koc"])} kênh</h2>
  <p class="sub">Ba nhóm điểm đo được: hiệu suất (tối đa 25), nội dung (25), hình ảnh/video (15). Tổng tối đa 65 — phần khán giả và hợp tác chưa có dữ liệu, không chấm.</p>
  <div class="card">
    <div class="legend">
      <span class="li"><span class="sw" style="background:var(--s1)"></span>Hiệu suất (25)</span>
      <span class="li"><span class="sw" style="background:var(--s2)"></span>Nội dung (25)</span>
      <span class="li"><span class="sw" style="background:var(--s3)"></span>Hình ảnh/video (15)</span>
    </div>
    <div class="chartbox tall"><canvas id="scoreChart" role="img" aria-label="Biểu đồ điểm đã đo của các KOC, xếp chồng theo 3 nhóm"></canvas></div>
    <details><summary>Xem dạng bảng</summary><div class="dbody"><div class="tblwrap"><table class="num">
      <thead><tr><th>KOC</th><th class="r">Hiệu suất /25</th><th class="r">Nội dung /25</th><th class="r">Hình ảnh /15</th><th class="r">Tổng đã đo /65</th></tr></thead>
      <tbody>{score_rows}</tbody></table></div></div></details>
  </div>
</section>''' if has_koc else ""

    val_pct = f'{100 * ck["val_pass"] / ck["val_total"]:.0f}%' if ck["val_total"] else "—"
    return f'''<!doctype html>
<html lang="vi">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Báo cáo KOC — {_e(d["product"])}</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&display=swap">
<style>{CSS}</style>
</head>
<body>
<div class="wrap">

<header class="top"><div class="toprow">
  <span class="brand">KOC Discovery · {_e(d["generated"])}</span>
  <nav class="chips">
    <a href="#tong-quan">Tổng quan</a><a href="#phieu">Sàng lọc</a><a href="#koc">KOC</a>
    <a href="#diem">Điểm</a><a href="#ngan-sach">Ngân sách</a><a href="#chi-phi">Chi phí</a>
    <a href="#do-tin-cay">Độ tin cậy</a><a href="#can-xac-minh">Cần xác minh</a>
  </nav>
</div></header>

<section id="tong-quan">
  <h1>Đề xuất {f["selected"]} KOC TikTok cho chiến dịch {_e(d["product"])}</h1>
  <p class="sub">Khách hàng mục tiêu: {_e(d["audience"])} · Ngân sách {_vn(d["budget_vnd"])} VNĐ ·
  Mục tiêu: {_e(obj_txt)} · Dữ liệu TikTok Shop VN {_e(d["period"])}</p>
  <div class="tiles">
    <div class="tile hero"><span class="v num">{f["selected"]} + {f["backups"]}</span><span class="l">KOC đề xuất + dự phòng</span><span class="n">Chọn từ {f["pool"]} ứng viên qua 5 vòng sàng lọc</span></div>
    <div class="tile"><span class="v num">{_vn(b["total"] or 0)}</span><span class="l">Tổng giá giả định của bộ (VNĐ)</span><span class="n">Giá thật cần xin báo giá</span></div>
    <div class="tile"><span class="v num">≈ {_vn(c["total_vnd"])}đ</span><span class="l">Chi phí nghiên cứu ({_vn(c["pct"], 2)}% ngân sách)</span><span class="n">{_vn(c["total_usd"], 2)} USD{" · chạy lại lần hai: 0đ" if c["warm_zero"] else ""}</span></div>
    <div class="tile"><span class="v num">{val_pct}</span><span class="l">Lý do có bằng chứng kiểm chứng</span><span class="n">{ck["val_pass"]}/{ck["val_total"]} lý do đạt</span></div>
  </div>
  <div class="callout"><b>Cách đọc báo cáo:</b> mỗi đề xuất kèm lý do, bằng chứng cụ thể (số liệu hoặc câu nói trong video kèm mốc thời gian) và việc cần xác minh trước khi chốt.
  Điểm hiển thị là <b>phần đã đo được (tối đa 65/100)</b> — 35 điểm còn lại (khán giả 25, hợp tác 10) không có dữ liệu để chấm, cần ảnh Analytics và báo giá thật. Hệ thống không đoán.</div>
</section>

<section id="phieu">
  <h2>Hành trình sàng lọc: {f["pool"]} ứng viên → {f["selected"]} lựa chọn</h2>
  <p class="sub">Mỗi vòng loại đều có lý do lưu lại. Vòng đắt tiền (xem video bằng AI) chỉ dành cho nhóm cuối cùng.</p>
  <div class="card"><div class="funnel">{funnel_html}</div></div>
  <div class="exc">{exc_pills}</div>
  {events}{relaxation}
  <p class="muted">Toàn bộ {f["exc_total"]} lượt loại kèm lý do trong file excluded.csv.</p>
</section>

<section id="koc">
  <h2>Bộ {f["selected"]} KOC đề xuất</h2>
  <p class="sub">Giá thuê là giả định theo nhóm kênh (chưa có dữ liệu giá thật). "Giá trần" = ngưỡng báo giá: vượt trần thì chuyển người dự phòng. Bấm từng mục để xem lý do, bằng chứng và việc cần xác minh.</p>
  {cards_html}
  {backup_html}
</section>

{score_section}
{sens_section}

<section id="chi-phi">
  <h2>Chi phí nghiên cứu &amp; thời gian</h2>
  <div class="tiles">
    <div class="tile"><span class="v num">{_vn(c["credits"], 1)} credit</span><span class="l">Dữ liệu Kalodata (≈ {_vn(c["kalodata_usd"], 2)} USD)</span><span class="n">{f["pool"]} kênh × 100 video + {f["videos"]} link video</span></div>
    <div class="tile"><span class="v num">{_vn(c["ai_usd"], 2)} USD</span><span class="l">Phân tích AI (≈ {_vn(c["ai_usd"] * USD_VND)}đ)</span><span class="n">{_vn(c["tin"])} chữ vào / {_vn(c["tout"])} chữ ra (token)</span></div>
    <div class="tile hero"><span class="v num">≈ {_vn(c["total_vnd"])}đ</span><span class="l">Tổng chi phí ({_vn(c["total_usd"], 2)} USD)</span><span class="n">{_vn(c["pct"], 2)}% ngân sách chiến dịch · tỷ giá tham khảo {_vn(USD_VND)}đ/USD</span></div>
    <div class="tile"><span class="v num">{"0đ" if c["warm_zero"] else "—"}</span><span class="l">Chạy lại lần hai (dữ liệu đã lưu)</span><span class="n">{"Đo thật: 0 credit, 0 token, 0 USD" if c["warm_zero"] else "Chưa có lần chạy ấm"}</span></div>
  </div>
  {cost_callout}
</section>

<section id="do-tin-cay">
  <h2>Độ tin cậy của kết quả — kiểm chứng tự động</h2>
  <div class="grid2">{resume_card}{val_card}{num_card}{rec_card}</div>
</section>

<section id="can-xac-minh">
  <h2>Việc cần làm trước khi chốt hợp đồng</h2>
  <div class="card">
    <ul class="tight">
      <li><b>Xin ảnh Analytics khán giả</b> của từng kênh ({_e(d["audience"])}) — hệ thống không có dữ liệu này và không đoán. Đây là 25/100 điểm chưa chấm.</li>
      <li><b>Xin báo giá thật</b> và so với giá trần từng người; vượt trần → chuyển dự phòng. Có báo giá thật, nhập lại để chọn bộ tối ưu mới.</li>
      <li><b>Chốt quyền sử dụng nội dung</b> (đăng lại, Spark Ads) và thời hạn — 10/100 điểm hợp tác chưa chấm.</li>
      <li><b>Duyệt kịch bản trước đăng</b>: bắt buộc nêu SPF/PA, lượng dùng, thoa lại; cấm claim tuyệt đối về an toàn và số liệu không nguồn; gắn nhãn quảng cáo rõ.</li>
      <li><b>Xem thêm video đúng ngách</b> của các kênh mà mẫu xem lệch ngành — mỗi kênh mới chỉ xem 2 video.</li>
      <li><b>Hỏi xung đột đối thủ</b> (danh sách hiện tại: {_e(competitors)} — AI đề xuất, thương hiệu cần xác nhận lại).</li>
      <li>Việc riêng từng kênh nằm trong thẻ KOC ở trên.</li>
    </ul>
  </div>
  <div class="callout warn"><b>Giới hạn nói thẳng:</b> doanh thu/lượt xem là ước tính của Kalodata, không kiểm chứng độc lập · nguồn video thiên về video có bán hàng · mẫu 2 video/kênh là chỉ báo, không phải kết luận toàn diện · bản chép lời tiếng Việt còn lỗi (đã gắn cờ chỗ nghi ngờ) · giá thuê là giả định minh họa · chưa đo chồng lấn khán giả giữa các kênh. Báo cáo này hỗ trợ quyết định, không thay thế bước xác minh của người làm chiến dịch.</div>
</section>

<footer>
  <span>Nguồn dữ liệu: Kalodata (TikTok Shop VN, {_e(d["period"])}) + phân tích AI trên {f["videos"]} video (khung hình + lời nói). Mọi con số chi phí/kiểm chứng đo từ nhật ký hệ thống, không ước tính suông.</span>
  <span>Run {_e(d["run_id"])} · dữ liệu đến {_e(d["as_of"])} · xuất {_e(d["generated"])} · file kèm: results.csv · excluded.csv · benchmark.md · report.md · resume_demo.json</span>
  <span>Liên hệ KOC: email/Zalo không hiển thị trong bản công khai; xem bản đầy đủ khi cần liên hệ.</span>
</footer>

</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script>
(function(){{
  if (typeof Chart === "undefined") return;
  var D = {dj};
  var css = function(n){{ return getComputedStyle(document.documentElement).getPropertyValue(n).trim(); }};
  var charts = [];
  function build(){{
    charts.forEach(function(c){{ c.destroy(); }}); charts = [];
    var ink2 = css("--ink2"), grid = css("--grid"), surface = css("--surface");
    Chart.defaults.font.family = css("--font") || "system-ui";
    Chart.defaults.color = ink2;
    function ds(label,data,color){{ return {{label:label,data:data,backgroundColor:color,borderColor:surface,borderWidth:2,borderRadius:4,borderSkipped:false,barPercentage:.72,categoryPercentage:.82}}; }}
    var sc = document.getElementById("scoreChart");
    if (sc && D.names.length) charts.push(new Chart(sc,{{
      type:"bar",
      data:{{labels:D.names,datasets:[ds("Hiệu suất",D.perf,css("--s1")),ds("Nội dung",D.cont,css("--s2")),ds("Hình ảnh/video",D.vis,css("--s3"))]}},
      options:{{indexAxis:"y",responsive:true,maintainAspectRatio:false,
        scales:{{x:{{stacked:true,max:65,grid:{{color:grid}},ticks:{{color:ink2,callback:function(v){{return v+"đ";}}}}}},
                y:{{stacked:true,grid:{{display:false}},ticks:{{color:ink2,font:{{size:12}}}}}}}},
        plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:function(c){{return c.dataset.label+": "+c.parsed.x.toFixed(2)+" điểm";}},
          footer:function(items){{var t=items.reduce(function(s,i){{return s+i.parsed.x;}},0);return "Tổng đã đo: "+t.toFixed(2)+" / 65";}}}}}}}}}}
    }}));
    var se = document.getElementById("sensChart");
    if (se && D.scen.length) charts.push(new Chart(se,{{
      type:"bar",
      data:{{labels:D.scen,datasets:[
        {{label:"Tổng giá bộ tối ưu",data:D.feasible,backgroundColor:css("--s1"),borderColor:surface,borderWidth:2,borderRadius:4,borderSkipped:false,barPercentage:.62,categoryPercentage:.8}},
        {{label:"Rẻ nhất có thể (vượt ngân sách)",data:D.cheapest,backgroundColor:css("--crit"),borderColor:surface,borderWidth:2,borderRadius:4,borderSkipped:false,barPercentage:.62,categoryPercentage:.8}},
        {{label:"Ngân sách",data:D.scen.map(function(){{return D.budget;}}),type:"line",borderColor:css("--muted"),borderWidth:2,borderDash:[6,4],pointRadius:0,fill:false}}
      ]}},
      options:{{responsive:true,maintainAspectRatio:false,
        scales:{{x:{{grid:{{display:false}},ticks:{{color:ink2}}}},
                y:{{grid:{{color:grid}},ticks:{{color:ink2,callback:function(v){{return v+" tr";}}}},title:{{display:true,text:"Triệu VNĐ",color:ink2,font:{{size:11}}}}}}}},
        plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:function(c){{
          if(c.dataset.type==="line") return "Ngân sách: "+(D.budget*1000000).toLocaleString("vi-VN")+"đ";
          if(c.parsed.y==null) return null;
          return c.dataset.label+": "+(c.parsed.y*1000000).toLocaleString("vi-VN")+"đ";}}}}}}}}}}
    }}));
  }}
  build();
  var mq = window.matchMedia("(prefers-color-scheme: dark)");
  if (mq.addEventListener) mq.addEventListener("change", build);
  new MutationObserver(function(){{ build(); }}).observe(document.documentElement,{{attributes:true,attributeFilter:["data-theme"]}});
}})();
</script>
</body>
</html>
'''


def render(ctx) -> Path:
    """Sinh dashboard.html cho run hiện tại. Gọi từ report.write_all."""
    d = collect(ctx)
    out = ctx.report_dir / "dashboard.html"
    out.write_text(_page(d), encoding="utf-8")
    return out
