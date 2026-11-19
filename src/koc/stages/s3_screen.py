"""S3 — cheap-LLM text screening (batched) + recall audit of the S2 cut.

Batch 10 creators/call keeps model calls ~O(N/10); closed schema -> code merges
scores. Recall audit: random ~10% of non-hard excluded creators re-screened;
if their would-be internal score beats the kept threshold, the funnel missed
them — reported honestly (plan §7.10, invisible-error measurement).
"""
from __future__ import annotations

import json
import random

from ..evidence import record
from ..llm import LLMUnavailable
from ..prompts import S3_SYSTEM, ScreenBatch
from ..scoring import ScoreCard, content_score_text
from . import s2_metrics

BATCH_SIZE = 10


def _state_for(ctx, cid, res_a, details, videos_limit=8):
    r = res_a.get(cid, {})
    d = details.get(cid, {})
    vids = sorted(r.get("videos", []), key=lambda v: -v.get("views", 0))[:videos_limit]
    m = r.get("metrics", {})
    return {
        "creator_id": cid,
        "name": d.get("name") or r.get("name", ""),
        "followers": d.get("followers") or r.get("followers", 0),
        "bio": (d.get("bio") or "")[:300],
        "video_titles": [v.get("title", "")[:120] for v in vids],
        "metrics": {k: m.get(k) for k in ("median_views", "median_er", "ad_ratio",
                                          "posts_per_week", "view_follower_ratio", "n_videos")},
        "niche_keyword_ratio": round(r.get("niche_ratio", 0), 3),
    }


def run(ctx) -> dict:
    s2 = s2_metrics.load(ctx)
    res_a = ctx.runner.done_results("s2a")
    cards = {k: ScoreCard(**v) for k, v in s2["cards"].items()}
    details = s2["details"]
    kept = s2["kept"]
    camp = ctx.campaign
    f = ctx.cfg.funnel
    rng = random.Random(ctx.cfg.seed)

    # batch theo thứ tự creator_id CANONICAL (không theo thứ hạng/completion order)
    # → cùng thành phần batch giữa các run → judgement cache hit khi replay (19/11)
    kept_canonical = sorted(kept)
    batches = [kept_canonical[i:i + BATCH_SIZE] for i in range(0, len(kept_canonical), BATCH_SIZE)]
    # recall audit: sample BOTH hard red-flag exclusions and score-cut exclusions —
    # measures whether the funnel (incl. absolute ER threshold) over-excludes
    cut_excluded = sorted((e for e in s2["excluded"] if e["stage"] == "s2a"),
                          key=lambda e: e["creator_id"])
    n_audit = max(1, round(len(cut_excluded) * float(ctx.cfg.raw["audit"]["excluded_sample_pct"]))) if cut_excluded else 0
    audit_ids = [e["creator_id"] for e in rng.sample(cut_excluded, min(n_audit, len(cut_excluded)))] if n_audit else []

    context = (f"Sản phẩm: {camp.get('product', 'kem chống nắng')}. "
               f"Ngách: {', '.join(camp.get('niche_keywords', []))}. "
               f"Đối thủ cần kiểm tra xung đột: {', '.join(camp.get('competitors', [])) or '(chưa có danh sách)'}. "
               f"Khán giả mục tiêu: {camp.get('audience', {})}.\n\n")

    def worker(item: str):
        if item == "audit":
            cids = audit_ids
        else:
            cids = batches[int(item.replace("batch", ""))]
        states = [_state_for(ctx, cid, res_a, details) for cid in cids]
        user = context + "<creator_data>\n" + json.dumps(states, ensure_ascii=False) + "\n</creator_data>"
        try:
            j = ctx.llm("screen", "s3").judge(S3_SYSTEM, user, ScreenBatch, entity_id=item)
            return {"results": [r.model_dump() for r in j.results]}
        except LLMUnavailable as e:
            # degrade: batch này không có sàng lọc ngữ nghĩa — creator bị cờ
            # screen_missing, điểm chỉ phần code, report ghi rõ; pipeline tiếp tục
            return {"results": [], "degraded": str(e)[:300]}

    items = [f"batch{i}" for i in range(len(batches))] + (["audit"] if audit_ids else [])
    ctx.runner.run("s3", items, worker, concurrency=int(ctx.cfg.raw["limits"]["llm_concurrency"]))
    results = ctx.runner.done_results("s3")

    judgements: dict[str, dict] = {}
    for item, r in results.items():
        for j in r.get("results", []):
            judgements[j["creator_id"]] = j

    # merge semantic fit + competitor + risk into cards
    for cid in kept:
        j = judgements.get(cid)
        card = cards[cid]
        if not j:
            card.flags.append({"flag": "screen_missing", "detail": "S3 không trả kết quả cho creator"})
            continue
        hits = sorted(set(j.get("competitor_names", [])) if j.get("competitor_mention") else set())
        r_a = res_a.get(cid, {})
        content, cparts = content_score_text(r_a.get("niche_ratio", 0),
                                             r_a.get("metrics", {}).get("ad_ratio", 0),
                                             hits, llm_fit=j.get("niche_fit"))
        card.content = content
        card.content_measured_max = cparts["measured_max"]
        if j.get("brand_risk", 0) > 0.6:
            card.flags.append({"flag": "brand_risk", "detail": f"LLM đánh giá rủi ro thương hiệu {j['brand_risk']:.2f}: {'; '.join(j.get('reasons', []))[:200]}"})
        if j.get("confidence", 1) < 0.5:
            card.flags.append({"flag": "low_confidence", "detail": "S3 confidence thấp — cần người duyệt"})
        card.niche_cluster = j.get("style_cluster", "other")
        record(ctx.db, ctx.cfg.run_id, "s3", "niche_signal", f"judgement:s3:{cid}",
               j, creator_id=cid)

    ranked = sorted((cards[cid] for cid in kept), key=lambda c: (-c.internal_rank_score(), c.creator_id))
    final_kept = [c.creator_id for c in ranked[:int(f["after_3"])]]
    threshold = ranked[len(final_kept) - 1].internal_rank_score() if final_kept else 0.0
    cut = [{"creator_id": c.creator_id, "name": details.get(c.creator_id, {}).get("name", ""),
            "stage": "s3", "hard": False,
            "reason": f"dưới ngưỡng S3 (điểm {c.internal_rank_score():.3f} < {threshold:.3f})",
            "measured": c.measured, "measured_max": c.measured_max}
           for c in ranked[len(final_kept):]]

    # recall audit evaluation — recompute performance percentiles against the
    # eligible pool (excluded cards carry default 0.5 pcts, not their true rank)
    from ..scoring import percentile_rank, performance_score
    cut_meta = ctx.stage_result("s2a_cut") or {}
    pools, mkeys = cut_meta.get("pools", {}), cut_meta.get("metric_keys", [])
    audit_misses = []
    for cid in audit_ids:
        j = judgements.get(cid)
        card = cards.get(cid)
        if not j or card is None:
            continue
        r_a = res_a.get(cid, {})
        m = r_a.get("metrics", {})
        pcts = {k: percentile_rank(m.get(k, 0), pools.get(k, [])) for k in mkeys} if m.get("n_videos") else {}
        perf, _ = performance_score(m, pcts, 25.0)
        content, cparts = content_score_text(r_a.get("niche_ratio", 0), m.get("ad_ratio", 0),
                                             j.get("competitor_names", []) if j.get("competitor_mention") else [],
                                             llm_fit=j.get("niche_fit"))
        hypothetical = ScoreCard(creator_id=cid, performance=perf,
                                 content=content, content_measured_max=cparts["measured_max"])
        if hypothetical.internal_rank_score() > threshold:
            audit_misses.append({"creator_id": cid,
                                 "would_be_score": hypothetical.internal_rank_score(),
                                 "threshold": threshold,
                                 "excluded_because": next((e["reason"] for e in s2["excluded"]
                                                           if e["creator_id"] == cid), "?")})
    audit = {"sampled": len(audit_ids), "misses": len(audit_misses),
             "rate": round(len(audit_misses) / len(audit_ids), 3) if audit_ids else None,
             "details": audit_misses,
             "note": "mẫu ngẫu nhiên KOC bị loại ở S2a, chấm lại S3; miss = điểm lẽ ra vượt ngưỡng giữ"}

    out = {"kept": final_kept, "excluded_cut": cut, "judgements": judgements,
           "cards": {k: v.model_dump() for k, v in cards.items()},
           "clusters": {cid: judgements.get(cid, {}).get("style_cluster", "other") for cid in kept},
           "audit": audit, "threshold": threshold,
           "degraded_batches": {it: r["degraded"] for it, r in results.items() if r.get("degraded")}}
    ctx.put_stage_result("s3", out)
    return out


def load(ctx) -> dict:
    r = ctx.stage_result("s3")
    return r if r else run(ctx)
