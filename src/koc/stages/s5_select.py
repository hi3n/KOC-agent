"""S5 — combinatorial portfolio selection (code) + evidence-grounded reasons (LLM).

Selection is exhaustive C(K,5) with hard budget/slot/diversity constraints —
deterministic, explainable, guaranteed (D13). LLM only phrases reasons from the
stored evidence store; validator rejects any claim citing non-existent or
foreign evidence, with one bounded retry.
"""
from __future__ import annotations

import json
from dataclasses import asdict

from .. import planner
from ..evidence import audit_numeric_claims, for_creator, validate_reason
from ..llm import LLMUnavailable
from ..prompts import S5_SYSTEM, ReasonSet, ReasonItem, Strength, VideosWatched
from ..scoring import ScoreCard
from ..select import Candidate, assign_tier, price_sensitivity, select_portfolio
from . import s2_metrics, s3_screen, s4_video

ROLE_LABEL = {"anchor": "chủ lực", "mid": "tầm trung", "micro": "tầm trung nhỏ", "nano": "nano thử nghiệm"}


def _template_reasons(blocks: list[dict]) -> ReasonSet:
    """Fallback S5 khi mọi LLM provider fail: lý do sự thật sinh bằng code từ
    evidence đã lưu — không văn hoa, vẫn truy vết được, vẫn pass validator."""
    items = []
    for b in blocks:
        strengths = []
        for e in b["evidence"]:
            if len(strengths) >= 3:
                break
            p, eid = e["payload"], e["evidence_id"]
            if e["kind"] == "metric" and "median_views" in p:
                strengths.append(Strength(
                    claim=f"View trung vị {p['median_views']:,.0f}/video (mẫu {p.get('n_videos', '?')} video); ER trung vị {p.get('median_er', 0):.4f}",
                    evidence_ids=[eid]))
            elif e["kind"] == "metric" and "visual_quality" in p:
                strengths.append(Strength(
                    claim=f"Điểm hình ảnh LLM: visual {p['visual_quality']:.2f}, demo {p['demo_quality']:.2f}, hook {p['hook_strength']:.2f}",
                    evidence_ids=[eid]))
            elif e["kind"] == "transcript_quote" and p.get("quote"):
                strengths.append(Strength(
                    claim=f"Dẫn chứng lời nói [{p.get('start_s', 0):.0f}s]: “{p['quote'][:120]}”",
                    evidence_ids=[eid]))
            elif e["kind"] == "frame_obs" and p.get("observations"):
                strengths.append(Strength(
                    claim=f"Quan sát khung hình: {p['observations'][0][:120]}", evidence_ids=[eid]))
        if not strengths and b["evidence"]:
            strengths.append(Strength(claim="Có bằng chứng đã lưu trong evidence store",
                                      evidence_ids=[b["evidence"][0]["evidence_id"]]))
        sc = b["scores"]
        items.append(ReasonItem(
            creator_id=b["creator_id"], role_in_campaign=b["role"],
            summary=(f"{b['name']} — {b['followers']:,} followers, tier {b['tier']}; "
                     f"điểm đã đo {sc['measured']}/{sc['measured_max']}. "
                     "[Lý do sinh bằng CODE từ evidence — LLM diễn đạt không khả dụng; "
                     "cần người viết lại trước khi gửi khách]"),
            strengths=strengths,
            concerns=[f["detail"] for f in b["flags"]][:3] + ["Lý do chưa qua LLM diễn đạt (degraded)"],
            videos_watched=VideosWatched(seen=b["videos_watched"]["seen"], total=b["videos_watched"]["total"]),
            verify_before_contract=["Ảnh Analytics khán giả (nữ 18-30, VN)",
                                    "Báo giá thật so với giá trần",
                                    "Quyền sử dụng nội dung / Spark Ads",
                                    "Thái độ hợp tác, lịch sử đúng hạn"]))
    return ReasonSet(reasons=items)


def run(ctx) -> dict:
    s4 = s4_video.load(ctx)
    s3 = s3_screen.load(ctx)
    s2 = s2_metrics.load(ctx)
    res_a = ctx.runner.done_results("s2a")
    cards = {k: ScoreCard(**v) for k, v in s4["cards"].items()}
    details = s2["details"]
    kept = s3["kept"]
    bcfg = ctx.cfg.raw["budget"]
    scfg = ctx.cfg.raw["selection"]

    cands = []
    for cid in kept:
        card, d = cards[cid], details.get(cid, {})
        followers = int(d.get("followers", 0))
        tier = assign_tier(followers, bcfg["tier_followers"])
        cands.append(Candidate(
            creator_id=cid, name=d.get("name", cid), followers=followers, tier=tier,
            price_vnd=float(bcfg["price_tiers_vnd"].get(tier, 5_000_000)),
            rank_score=card.internal_rank_score(), coverage=card.measured_max / 65.0,
            niche_cluster=card.niche_cluster, measured=card.measured,
            measured_max=card.measured_max))

    sel = select_portfolio(cands, total_vnd=float(bcfg["total_vnd"]), slots=scfg["slots"],
                           size=5, max_per_cluster=int(scfg["max_per_niche_cluster"]))
    s5_decision = planner.decide_after_s5(ctx, sel)
    if not sel["feasible"]:
        out = {"selection": {"feasible": False, "infeasible_reason": sel["infeasible_reason"]},
               "reasons": [], "validation": {}, "sensitivity": [],
               "plan_decision": s5_decision.model_dump()}
        ctx.put_stage_result("s5", out)
        return out

    portfolio = sel["portfolios"][0]
    backups = sel["backups"][:int(scfg["backups"])]
    seen = {r["creator_id"]: r["n"] for r in ctx.db.query(
        "SELECT creator_id, COUNT(*) n FROM videos WHERE run_id=? AND status='processed'"
        " GROUP BY creator_id", (ctx.cfg.run_id,))}

    def creator_block(c: Candidate, role: str):
        card = cards[c.creator_id]
        # trim evidence cho prompt gọn (sonnet timeout với prompt lớn — 19/11):
        # ưu tiên quote/observation/score video rồi metrics; tối đa 12/creator
        prio = {"transcript_quote": 0, "frame_obs": 1, "metric": 2, "niche_signal": 3}
        ev = sorted(for_creator(ctx.db, ctx.cfg.run_id, c.creator_id),
                    key=lambda e: (prio.get(e["kind"], 9), e["evidence_id"]))[:12]
        return {
            "creator_id": c.creator_id, "name": c.name, "role": role,
            "tier": c.tier, "followers": c.followers,
            "price_assumed_vnd": c.price_vnd,
            "price_ceiling_vnd": portfolio["price_ceiling_vnd"].get(c.creator_id),
            "scores": {"measured": card.measured, "measured_max": card.measured_max,
                       "performance": card.performance, "content": card.content,
                       "visual": card.visual,
                       "unmeasured": ["audience (25đ): cần ảnh Analytics thật",
                                      "collaboration (10đ): giá thật, thái độ, quyền nội dung"]},
            "flags": card.flags,
            "videos_watched": {"seen": seen.get(c.creator_id, 0),
                               "total": res_a.get(c.creator_id, {}).get("n_total", 0)},
            "evidence": [{"evidence_id": e["evidence_id"], "kind": e["kind"],
                          "payload": e["payload"]} for e in ev],
        }

    blocks = [creator_block(c, ROLE_LABEL.get(c.tier, c.tier)) for c in portfolio["members"]]
    blocks += [creator_block(c, "dự phòng") for c in backups]
    camp = ctx.campaign
    user = (
        f"Chiến dịch: {camp.get('product', 'kem chống nắng')} | mục tiêu {camp.get('objective')} | "
        f"khán giả {camp.get('audience')} | ngân sách {bcfg['total_vnd']:,} VNĐ.\n"
        f"Bộ đã chọn (thuật toán): tổng giá giả định {portfolio['total_price_vnd']:,} VNĐ, "
        f"hệ số giá tối đa {portfolio['max_price_scale']}, giá trần từng người trong block.\n"
        f"<portfolio_and_evidence>\n{json.dumps(blocks, ensure_ascii=False, default=str)}\n</portfolio_and_evidence>\n"
        "Viết ReasonSet cho đúng 7 creator (5 chính + 2 dự phòng), theo schema.")
    def _full_validate(reasons_list: list[ReasonItem]) -> dict[str, list[str]]:
        r_dicts = [r.model_dump() for r in reasons_list]
        val = {r["creator_id"]: validate_reason(ctx.db, ctx.cfg.run_id, r) for r in r_dicts}
        num_res = audit_numeric_claims(ctx.db, ctx.cfg.run_id, r_dicts, details)
        for um in num_res.get("unmatched", []):
            cid_u = um["creator_id"]
            val.setdefault(cid_u, []).append(
                f"strength[{um['strength_idx']}] nêu con số {um['number']:g} không khớp dữ liệu gốc"
            )
        return val

    reason_llm = ctx.llm("reason", "s5")
    degraded = None
    try:
        rs: ReasonSet = reason_llm.judge(S5_SYSTEM, user, ReasonSet, entity_id="portfolio")
        validation = _full_validate(rs.reasons)
        bad = {cid: iss for cid, iss in validation.items() if iss}
        if bad:
            user2 = user + ("\n\nLẦN TRƯỚC VI PHẠM KIỂM CHỨNG — sửa đúng các lỗi sau, "
                            "chỉ trích evidence_ids có thật trong kho của từng creator:\n"
                            + json.dumps(bad, ensure_ascii=False))
            rs2: ReasonSet = reason_llm.judge(S5_SYSTEM, user2, ReasonSet, entity_id="portfolio_retry")
            v2 = _full_validate(rs2.reasons)
            merged = {r.creator_id: r for r in rs.reasons}
            for r in rs2.reasons:
                if not v2.get(r.creator_id):
                    merged[r.creator_id] = r
            rs = ReasonSet(reasons=list(merged.values()))
            validation = _full_validate(rs.reasons)
    except LLMUnavailable as e:
        # DEGRADE, DON'T STOP: lý do sinh bằng CODE từ evidence thật (vẫn pass
        # validator), đánh dấu rõ để người viết lại trước khi gửi khách
        degraded = str(e)[:300]
        rs = _template_reasons(blocks)
        validation = {r.creator_id: validate_reason(ctx.db, ctx.cfg.run_id, r.model_dump())
                      for r in rs.reasons}

    sensitivity = price_sensitivity(
        cands, total_vnd=float(bcfg["total_vnd"]), slots=scfg["slots"],
        price_tiers=bcfg["price_tiers_vnd"], scenarios=bcfg.get("scale_scenarios", [1.0]),
        max_per_cluster=int(scfg["max_per_niche_cluster"]))

    out = {
        "selection": {
            "feasible": True,
            "portfolios": [{**p, "members": [asdict(c) for c in p["members"]]}
                           for p in sel["portfolios"]],
            "backups": [asdict(c) for c in backups],
            "relaxation_used": sel["relaxation_used"],
        },
        "reasons": [r.model_dump() for r in rs.reasons],
        "reasons_degraded": degraded,
        "validation": validation,
        "sensitivity": sensitivity,
        "plan_decision": s5_decision.model_dump(),
    }
    ctx.put_stage_result("s5", out)
    return out


def load(ctx) -> dict:
    r = ctx.stage_result("s5")
    return r if r else run(ctx)
