"""Bounded Planner at 3 explicit decision points, always gated by Governor.

Decision points (avoiding unbounded ReAct loops while keeping self-adaptation):
1. After S2a cut: if survivors < target_size -> propose expanding S1 candidates.
2. After S4 video judgement: if an off-niche finalist still has unseen niche-matching
   videos in cached S2a rank -> propose inspecting 1 extra video (gated by Governor).
3. After S5 selection: record portfolio choice / constraint relaxation / infeasibility.
"""
from __future__ import annotations

from pydantic import BaseModel


class PlanDecision(BaseModel):
    point: str
    action: str
    target: str = ""
    rationale: str
    est_credits: float = 0.0
    is_replan: bool = False
    allowed: bool = True
    governor_note: str = ""


def _niche_hits(title: str, keywords: list[str]) -> int:
    if not title or not keywords:
        return 0
    t = title.lower()
    return sum(1 for k in keywords if k.lower() in t)


def decide_after_s2(ctx, kept: list[str], target_size: int = 5) -> PlanDecision:
    if len(kept) < target_size:
        target = f"kept={len(kept)}<{target_size}"
        rationale = (f"Thiếu ứng viên sau S2a ({len(kept)} < {target_size}) để lập bộ {target_size} — "
                     "đề xuất mở rộng lát cắt S1 hoặc nới ngưỡng lọc")
        ok, gnote = ctx.governor.authorize(
            "s2", "expand_candidates", target=target, actor="planner",
            est_credits=0.4, is_replan=True, reason=rationale,
            payload={"kept_count": len(kept), "target_size": target_size},
        )
        return PlanDecision(
            point="after_s2", action="expand_candidates", target=target,
            rationale=rationale, est_credits=0.4, is_replan=True,
            allowed=ok, governor_note=gnote,
        )
    target = f"kept={len(kept)}"
    rationale = f"Đủ {len(kept)} ứng viên (>= {target_size}), tiếp tục S2b/S3"
    ok, gnote = ctx.governor.authorize(
        "s2", "proceed", target=target, actor="planner", reason=rationale,
        payload={"kept_count": len(kept), "target_size": target_size},
    )
    return PlanDecision(
        point="after_s2", action="proceed", target=target,
        rationale=rationale, allowed=ok, governor_note=gnote,
    )


def decide_after_s4(ctx, kept: list[str], res_a: dict, video_judgements: dict,
                    keywords: list[str], max_proposals: int = 2) -> list[PlanDecision]:
    vrows = ctx.db.query("SELECT video_id, creator_id FROM videos WHERE run_id=?", (ctx.cfg.run_id,))
    v2c = {r["video_id"]: r["creator_id"] for r in vrows}
    judged_by_cid: dict[str, list[dict]] = {}
    seen_vids_by_cid: dict[str, set[str]] = {}

    for vid_, j in video_judgements.items():
        cid = v2c.get(vid_)
        if not cid:
            for k in kept:
                if any(v.get("video_id") == vid_ for v in res_a.get(k, {}).get("videos", [])):
                    cid = k
                    break
        if cid:
            judged_by_cid.setdefault(cid, []).append(j)
            seen_vids_by_cid.setdefault(cid, set()).add(vid_)

    decisions: list[PlanDecision] = []
    for cid in sorted(kept):
        if len(decisions) >= max_proposals:
            break
        vjs = judged_by_cid.get(cid, [])
        if not vjs:
            continue
        needs_niche_check = all(abs(float(j.get("knowledge_accuracy", 0.5)) - 0.5) < 1e-6 for j in vjs)
        if not needs_niche_check:
            continue
        seen_ids = seen_vids_by_cid.get(cid, set())
        unseen_niche = [
            v for v in res_a.get(cid, {}).get("videos", [])
            if v.get("video_id") not in seen_ids and _niche_hits(v.get("title", ""), keywords) > 0
        ]
        if not unseen_niche:
            continue
        cand = sorted(unseen_niche, key=lambda v: (-_niche_hits(v.get("title", ""), keywords),
                                                 -(v.get("revenue") or 0), v.get("video_id", "")))[0]
        target = f"{cid}:{cand['video_id']}"
        rationale = (f"Video mẫu chưa chạm kiến thức chống nắng nhưng kho cache s2a còn video khớp từ khóa ngách "
                     f"({cand.get('title', '')[:60]}) — đề xuất xem thêm 1 video (0.5cr)")
        ok, gnote = ctx.governor.authorize(
            "s4", "inspect_extra_video", target=target, actor="planner",
            est_credits=0.5, est_usd=0.02, is_replan=True, reason=rationale,
            payload={"creator_id": cid, "video_id": cand["video_id"], "title": cand.get("title", "")[:120]},
        )
        decisions.append(PlanDecision(
            point="after_s4", action="inspect_extra_video", target=target,
            rationale=rationale, est_credits=0.5, is_replan=True,
            allowed=ok, governor_note=gnote,
        ))

    if not decisions:
        rationale = "Hoàn tất chấm video đại diện S4; không cần bổ sung video ngoài kế hoạch"
        ok, gnote = ctx.governor.authorize(
            "s4", "proceed", target="s4_complete", actor="planner", reason=rationale,
        )
        decisions.append(PlanDecision(
            point="after_s4", action="proceed", target="s4_complete",
            rationale=rationale, allowed=ok, governor_note=gnote,
        ))
    return decisions


def decide_after_s5(ctx, sel: dict) -> PlanDecision:
    if not sel.get("feasible"):
        rationale = str(sel.get("infeasible_reason") or "Không tìm được bộ KOC khả thi")
        ok, gnote = ctx.governor.authorize(
            "s5", "report_infeasible", target="portfolio", actor="planner", reason=rationale,
        )
        return PlanDecision(
            point="after_s5", action="report_infeasible", target="portfolio",
            rationale=rationale, allowed=ok, governor_note=gnote,
        )
    if sel.get("relaxation_used"):
        rel = str(sel["relaxation_used"])
        rationale = f"Nới ràng buộc: {rel}"
        ok, gnote = ctx.governor.authorize(
            "s5", "relax_constraints", target=rel, actor="planner",
            is_replan=True, reason=rationale,
        )
        return PlanDecision(
            point="after_s5", action="relax_constraints", target=rel,
            rationale=rationale, is_replan=True, allowed=ok, governor_note=gnote,
        )
    total_vnd = sel["portfolios"][0]["total_price_vnd"]
    rationale = f"Chọn PA1 tối ưu toàn cục trong ngân sách ({total_vnd:,.0f} VNĐ)"
    ok, gnote = ctx.governor.authorize(
        "s5", "select_portfolio", target="PA1", actor="planner", reason=rationale,
        payload={"total_price_vnd": total_vnd},
    )
    return PlanDecision(
        point="after_s5", action="select_portfolio", target="PA1",
        rationale=rationale, allowed=ok, governor_note=gnote,
    )
