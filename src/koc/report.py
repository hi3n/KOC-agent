"""Outputs: results.csv, excluded.csv, report.md, benchmark.md.

Every number comes from the ledger or stored stage results — nothing estimated
in prose. Scores display measured/unmeasured split (never a fake /100). Reasons
render with their evidence payloads so a human can audit the chain.
"""
from __future__ import annotations

import csv
import json

from .evidence import audit_numeric_claims
from .scoring import ScoreCard

CREDIT_USD = 0.1  # tham khảo, ghi rõ trong benchmark


def _stage(ctx, name, default=None):
    r = ctx.stage_result(name)
    return r if r is not None else (default or {})


def write_all(ctx):
    out = ctx.run_dir
    out.mkdir(parents=True, exist_ok=True)
    s1, s2, s3, s4, s5 = (_stage(ctx, k) for k in ("s1", "s2", "s3", "s4", "s5"))
    details = s2.get("details", {})
    cards = {k: ScoreCard(**v) for k, v in s4.get("cards", s3.get("cards", {})).items()}
    reasons = {r["creator_id"]: r for r in s5.get("reasons", [])}
    sel = s5.get("selection", {})
    _csv_results(out, sel, reasons, cards, details)
    _csv_excluded(out, s2, s3)
    _report_md(ctx, out, s1, s2, s3, s4, s5, cards, reasons, details)
    write_benchmark(ctx)


def _csv_results(out, sel, reasons, cards, details):
    rows = []
    portfolios = sel.get("portfolios", [])
    p0 = portfolios[0] if portfolios else {}
    members = p0.get("members", []) + sel.get("backups", [])
    for m in members:
        cid = m["creator_id"]
        d = details.get(cid, {})
        card = cards.get(cid)
        r = reasons.get(cid, {})
        contacts = d.get("contacts", {})
        rows.append({
            "creator_id": cid, "name": m.get("name", d.get("name", "")),
            "handle": d.get("handle", ""), "role": r.get("role_in_campaign", m.get("tier", "")),
            "tier": m.get("tier", ""), "followers": m.get("followers", ""),
            "measured": card.measured if card else "", "measured_max": card.measured_max if card else "",
            "performance": card.performance if card else "", "content": card.content if card else "",
            "visual": card.visual if card else "",
            "price_assumed_vnd": m.get("price_vnd", ""),
            "price_ceiling_vnd": p0.get("price_ceiling_vnd", {}).get(cid, ""),
            "niche_cluster": m.get("niche_cluster", ""),
            "summary": r.get("summary", ""),
            "contact_tiktok": contacts.get("creator_contact_tiktok", ""),
            "contact_email": contacts.get("creator_contact_email", ""),
            "contact_zalo": contacts.get("creator_contact_zalo", ""),
            "flags": "; ".join(f["flag"] for f in (card.flags if card else [])),
        })
    if rows:
        with open(out / "results.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)


def _csv_excluded(out, s2, s3):
    rows = s2.get("excluded", []) + s3.get("excluded_cut", [])
    if rows:
        with open(out / "excluded.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["creator_id", "name", "stage", "hard", "reason",
                                              "measured", "measured_max"], extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)


def _fmt_money(v):
    try:
        return f"{float(v):,.0f}"
    except (TypeError, ValueError):
        return str(v)


def _report_md(ctx, out, s1, s2, s3, s4, s5, cards, reasons, details):
    cfg = ctx.cfg
    a = cfg.brief_analysis
    camp = ctx.campaign
    sel = s5.get("selection", {})
    L = []
    L.append(f"# Báo cáo đề xuất KOC — {camp.get('product', 'kem chống nắng')}\n")
    L.append(f"`run_id={cfg.run_id}` · as_of={cfg.as_of} · date_range={cfg.date_range} · seed={cfg.seed}\n")
    models = {r: cfg.llm_role(r).model for r in ("brief", "screen", "video", "reason")}
    L.append(f"Models (cấu hình được, không fix cứng): `{json.dumps(models)}`\n")

    L.append("\n## 1. Brief và phân tích của AI (S0)\n")
    L.append(f"> {cfg.brief_text.strip()[:600]}\n")
    if a:
        L.append(f"- Sản phẩm: **{a.product}**; mục tiêu: **{a.objective}**; khán giả: {a.audience_gender} {a.audience_age_range} ({a.audience_region})")
        L.append(f"- Danh mục Kalodata: {list(zip(a.category_ids, a.category_names))}")
        L.append(f"- Từ khóa ngách: {', '.join(a.niche_keywords)}")
        L.append(f"- Đối thủ (AI đề xuất — **giả định, cần thương hiệu xác nhận**): {', '.join(a.competitors) or '(trống)'}")
        L.append(f"- Ngân sách: {_fmt_money(a.budget_vnd)} VNĐ")
        L.append(f"- AI hiểu brief: {a.rationale}")
    L.append("\n## 2. Phễu\n")
    L.append("| Tầng | Vào | Ra | Ghi chú |")
    L.append("|---|---|---|---|")
    L.append(f"| S1 rank đa lát cắt | — | {len(s1.get('pool', []))} | dedupe round-robin, INDEPENDENT |")
    L.append(f"| S2a video stats + code | {len(s1.get('pool', []))} | {len(s2.get('kept', [])) + len([e for e in s2.get('excluded', []) if e['stage'] == 's2b'])} | loại cứng + cắt |")
    L.append(f"| S2b detail | — | {len(s2.get('kept', []))} | bio, contacts, follower spike |")
    L.append(f"| S3 text LLM | {len(s2.get('kept', []))} | {len(s3.get('kept', []))} | batch {10}/call |")
    L.append(f"| S4 video LLM | {len(s3.get('kept', []))} | {s4.get('videos_planned', 0)} video | 2 video đại diện/creator |")
    L.append(f"| S5 chọn tổ hợp | {len(s3.get('kept', []))} | 5 + {len(sel.get('backups', []))} dự phòng | code, ràng buộc cứng |")
    for ev in s4.get("events", []):
        L.append(f"- Sự kiện: {ev}")
    if sel.get("relaxation_used"):
        L.append(f"- **Nới ràng buộc**: {sel['relaxation_used']} (ghi rõ, không âm thầm)")

    L.append("\n## 3. Đề xuất\n")
    L.append("*Lưu ý chất lượng đọc đúng: điểm hiệu suất đo trên TOÀN bộ video lấy được (tối đa 100), "
             "nhưng phân tích nội dung AI chỉ trên 2 video đại diện/creator. Nếu video mẫu lạc ngách "
             "chống nắng, lý do sẽ nói thẳng và checklist yêu cầu xem thêm video đúng ngách trước khi chốt — "
             "hệ thống không giấu khoảng trống bằng chứng. Ngách fit hiện là trọng số mềm, chưa gate cứng "
             "(hướng mở rộng: tăng trọng số semantic fit + thêm credit cho video analysis).*\n")
    if not sel.get("feasible"):
        L.append(f"**KHÔNG khả thi**: {sel.get('infeasible_reason')}\n")
    portfolios = sel.get("portfolios", [])
    if portfolios:
        p0 = portfolios[0]
        for m in p0["members"] + sel.get("backups", []):
            cid = m["creator_id"]
            d = details.get(cid, {})
            card = cards.get(cid)
            r = reasons.get(cid, {})
            is_backup = m in sel.get("backups", [])
            L.append(f"\n### {'[DỰ PHÒNG] ' if is_backup else ''}{m.get('name', cid)} (@{str(d.get('handle', '?')).lstrip('@')}) — {r.get('role_in_campaign', m.get('tier'))}\n")
            if card:
                L.append(f"**Điểm đã đo: {card.measured}/{card.measured_max}** "
                         f"(hiệu suất {card.performance}/25 · nội dung {card.content}/25 [phần đo {card.content_measured_max}/25] · hình ảnh {card.visual}/15)")
                L.append(f"**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.")
                if card.flags:
                    L.append("Cờ: " + "; ".join(f"`{f['flag']}` {f['detail']}" for f in card.flags))
            if r:
                L.append(f"\n{r.get('summary', '')}\n")
                for s in r.get("strengths", []):
                    L.append(f"- {s['claim']}  ")
                    L.append(f"  ↳ bằng chứng: `{', '.join(s.get('evidence_ids', []))}`")
                vw = r.get("videos_watched", {})
                L.append(f"- Đã xem **{vw.get('seen', '?')}/{vw.get('total', '?')}** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).")
                if r.get("concerns"):
                    L.append("- Lưu ý: " + "; ".join(r["concerns"]))
                ceiling = p0.get("price_ceiling_vnd", {}).get(cid)
                ceiling_txt = (f"**{_fmt_money(ceiling)} VNĐ** (báo giá vượt trần → chuyển dự phòng)"
                               if ceiling is not None else
                               "áp trần của slot thay thế (dự phòng không nằm trong phân bổ ngân sách hiện tại)")
                L.append(f"- Giá giả định: {_fmt_money(m.get('price_vnd'))} VNĐ · giá trần: {ceiling_txt}")
                if r.get("verify_before_contract"):
                    L.append("- Xác minh trước chốt: " + "; ".join(r["verify_before_contract"]))
            issues = s5.get("validation", {}).get(cid, [])
            if issues:
                L.append(f"- ⚠️ Lý do CHƯA pass kiểm chứng: {'; '.join(issues)}")
            contacts = d.get("contacts", {})
            if contacts:
                L.append("- Liên hệ: " + ", ".join(f"{k.replace('creator_contact_', '')}={v}" for k, v in contacts.items()))
        if len(portfolios) > 1:
            L.append("\n**Phương án thay thế** (chênh lệch điểm so với phương án 1):")
            for i, p in enumerate(portfolios[1:], 2):
                L.append(f"- PA{i}: {', '.join(m['name'] for m in p['members'])} · điểm {p['total_score']} (Δ {p['total_score'] - p0['total_score']:+.4f}) · giá {_fmt_money(p['total_price_vnd'])}")
            swaps = p0.get("swap_options", {})
            if swaps:
                L.append("\nHoán đổi 1 người (phương án 1): " + "; ".join(
                    f"{details.get(cid, {}).get('name', cid)} → {sw['name']} (Δ điểm {sw['score_delta']:+.4f})"
                    if sw else f"{details.get(cid, {}).get('name', cid)} → không có phương án tốt hơn"
                    for cid, sw in swaps.items()))

    L.append("\n## 4. Ngân sách (GIẢ ĐỊNH — không phải báo giá)\n")
    if portfolios:
        p0 = portfolios[0]
        L.append(f"- Tổng giá giả định bộ 5: **{_fmt_money(p0['total_price_vnd'])} VNĐ** / ngân sách {_fmt_money(cfg.raw['budget']['total_vnd'])}")
        L.append(f"- **Hệ số giá tối đa còn khả thi: {p0['max_price_scale']}** (giá thật cao hơn mức này → vượt ngân sách, dùng phương án thay thế)")
        L.append("- Bảng giá theo tier là minh họa; chỉ tỷ lệ tương đối có ý nghĩa. Điểm chất lượng KHÔNG dùng giá.")
    sens = s5.get("sensitivity", [])
    if len(sens) > 1:
        L.append("\n| price_scale | khả thi | tổng giá (VNĐ) | bộ 5 tối ưu / ghi chú |")
        L.append("|---|---|---|---|")
        for s in sens:
            cell = (", ".join(details.get(c, {}).get("name", c) for c in s["best_members"])
                    if s["feasible"] else (s.get("infeasible_reason") or "vô nghiệm"))
            L.append(f"| {s['price_scale']}x | {'✓' if s['feasible'] else '✗'} | "
                     f"{_fmt_money(s['best_total_vnd']) if s['best_total_vnd'] else '—'} | {cell} |")

    L.append("\n## 5. Kiểm tra mức bỏ sót (recall audit)\n")
    audit = s3.get("audit", {})
    L.append(f"- Mẫu ngẫu nhiên KOC bị loại ở S2a: **{audit.get('sampled', 0)}** người, chấm lại S3.")
    L.append(f"- Số người lẽ ra vượt ngưỡng giữ: **{audit.get('misses', 0)}** (tỷ lệ {audit.get('rate')}).")
    for m in audit.get("details", []):
        L.append(f"  - {m['creator_id']}: điểm lẽ ra {m['would_be_score']:.3f} > ngưỡng {m['threshold']:.3f}")
    L.append(f"- Toàn bộ danh sách loại kèm lý do: `excluded.csv` ({len(s2.get('excluded', [])) + len(s3.get('excluded_cut', []))} người).")

    L.append("\n## 6. Chi phí & hiệu năng\nXem `benchmark.md` (ledger đo thật, lạnh/ấm tách riêng).\n")
    t = ctx.ledger.totals()
    L.append(f"- Tổng: {t['credits']:.1f} credit Kalodata · {t['tin']:,} token in / {t['tout']:,} out (cache {t['tcached']:,}) · AI ${t['cost']:.4f} · {t['n']} lời gọi ghi ledger.")

    L.append("\n## 7. Giới hạn & hướng mở rộng\n")
    L.append("- Không dữ liệu khán giả/giá thuê → 35/100 điểm không tự chấm; kết luận ngân sách theo giả định.")
    L.append("- video/rank thiên video có doanh thu; mẫu 2 video/creator; doanh thu Kalodata là ước tính của họ.")
    L.append("- ASR tiếng Việt đo trên mẫu nhỏ; transcript lỗi → cờ, không kết luận im lặng.")
    L.append("- Chưa làm: Jev judge, Google Sheets, Batch API (−50%), human baseline, vòng phản hồi sau chiến dịch, chồng lấn khán giả thật.")
    L.append("- Mở rộng 500: đổi funnel.candidates + after_2a/after_3, thêm credit; kiến trúc không đổi (mọi tầng parameterized, cache/resume giữ nguyên).")
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")


def write_benchmark(ctx):
    out = ctx.run_dir
    db = ctx.db
    rid = ctx.cfg.run_id
    L = [f"# Benchmark — run `{rid}`\n",
         "Mọi số từ `usage_ledger` (đo thật). Credit→USD quy đổi tham khảo 0.1.\n"]
    for label, hit in (("LẠNH (cache trống, trả tiền thật)", 0), ("ẤM (cache hit, resume/replay)", 1)):
        rows = db.query(
            "SELECT stage, provider, COUNT(*) n, SUM(credits) credits, SUM(tokens_in) tin,"
            " SUM(tokens_out) tout, SUM(tokens_cached) tcached, SUM(cost_usd) cost,"
            " AVG(latency_ms) avg_ms FROM usage_ledger WHERE run_id=? AND cache_hit=?"
            " GROUP BY stage, provider ORDER BY stage, provider", (rid, hit))
        if not rows:
            continue
        L.append(f"\n## Lần chạy {label}\n")
        L.append("| Tầng | Provider | Calls | Credit | Token in | Token out | Cache tokens | AI USD | Avg ms |")
        L.append("|---|---|---|---|---|---|---|---|---|")
        for r in rows:
            L.append(f"| {r['stage']} | {r['provider']} | {r['n']} | {r['credits'] or 0:.1f} | "
                     f"{r['tin'] or 0:,} | {r['tout'] or 0:,} | {r['tcached'] or 0:,} | "
                     f"{(r['cost'] or 0):.4f} | {(r['avg_ms'] or 0):.0f} |")
        tot = db.one("SELECT SUM(credits) c, SUM(cost_usd) cost, SUM(tokens_in)+SUM(tokens_out) t,"
                     " SUM(latency_ms) ms FROM usage_ledger WHERE run_id=? AND cache_hit=?", (rid, hit))
        L.append(f"\n**Tổng {label.split('(')[0].strip()}**: {tot['c'] or 0:.1f} credit · "
                 f"${tot['cost'] or 0:.4f} AI · {tot['t'] or 0:,} token · {((tot['ms'] or 0) / 1000):.0f}s tổng thời gian tác vụ (song song nên wall-clock nhỏ hơn).")

    # unit costs + naive extrapolation (measured units, stated assumptions)
    v = db.one("SELECT AVG(cost_usd) c, COUNT(*) n FROM usage_ledger WHERE run_id=? AND stage='s4'"
               " AND provider='llm' AND cache_hit=0", (rid,))
    s2a = db.one("SELECT COUNT(*) n, SUM(credits) c FROM usage_ledger WHERE run_id=? AND stage='s2a'"
                 " AND provider='kalodata' AND cache_hit=0", (rid,))
    if v and v["n"]:
        video_unit_usd = (v["c"] or 0) + 0.5 * CREDIT_USD
        n500_naive = 500 * 5 * video_unit_usd + 500 * 0.2 * CREDIT_USD
        n500_funnel = (500 * 0.1 + 100 * 0.1 + 75 * 0.5) * CREDIT_USD + 75 * (v["c"] or 0) + 0.1
        L.append("\n## Ngoại suy N=500 (đơn giá ĐO được, giả định ghi rõ)\n")
        L.append(f"- Đơn giá phân tích 1 video (đo): LLM ${v['c'] or 0:.4f} + video/url 0.5cr = **${video_unit_usd:.4f}**")
        L.append(f"- Ngây thơ (500 KOC × 5 video, không phễu): ≈ **${n500_naive:.2f}** + Kalodata")
        L.append(f"- Phễu (500→100→20→5, 75 video, tỷ lệ theo plan): ≈ **${n500_funnel:.2f}**")
        L.append(f"- **Giảm ≈ {100 * (1 - n500_funnel / n500_naive):.0f}%** chi phí phân tích video. Giả định: tỷ lệ sống sót 500→100→20, 3 video/KOC top-20; đo lại khi chạy 500 thật.")
    L.append("\n## Phục hồi (resume)\n")
    L.append("- Warm ở trên = toàn bộ pipeline chạy lại với cache giữ nguyên: credit/token/cost thêm phải = 0 cho phần đã xong.")
    L.append("- Kill -9 demo: xem `resume_demo.json` (nếu có) — script chạy, kill giữa chừng, resume, so kết quả + chi phí thêm.")
    demo = out / "resume_demo.json"
    if demo.exists():
        d = json.loads(demo.read_text(encoding="utf-8"))
        L.append(f"```\n{json.dumps(d, ensure_ascii=False, indent=1)}\n```")

    s5 = _stage(ctx, "s5")
    s2 = _stage(ctx, "s2")
    if s5.get("reasons"):
        num_audit = audit_numeric_claims(db, rid, s5["reasons"], s2.get("details", {}))
        val = s5.get("validation", {})
        val_pass = sum(1 for v in val.values() if not v)
        L.append("\n## Kiểm chứng bằng chứng & số liệu (Validator + Numeric Audit)\n")
        L.append(f"- **Tỷ lệ lý do pass `validate_reason` (mã `evidence_id` hợp lệ + `videos_watched` khớp DB):** **{val_pass}/{len(val)}** ({100 * val_pass / max(len(val), 1):.0f}%)")
        L.append(f"- **Dry-run Numeric Claim Audit (đối chiếu con số trong `strengths.claim` với dữ liệu gốc):**")
        L.append(f"  - Khớp trực tiếp trong `evidence_id` được trích tại dòng đó: **{num_audit['in_cited_evidence']}/{num_audit['total_numbers']}** ({num_audit['cited_match_rate'] * 100:.1f}%)")
        L.append(f"  - Khớp trong bản ghi evidence/hồ sơ khác của cùng creator: **{num_audit['in_creator_other_evidence']}/{num_audit['total_numbers']}**")
        L.append(f"  - Tổng số liệu truy nguyên được về dữ liệu gốc: **{num_audit['verified_total']}/{num_audit['total_numbers']}** ({num_audit['verified_rate'] * 100:.1f}% · số không khớp: {len(num_audit['unmatched'])})")
    (out / "benchmark.md").write_text("\n".join(L), encoding="utf-8")
