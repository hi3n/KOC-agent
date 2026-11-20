"""S2 — code-side metrics funnel (D8/D9).

S2a: video/rank for EVERY candidate (0.1cr, <=100 rows same price) -> self-computed
ER, median/mean views, view/follower, stability, frequency, ad ratio, niche keyword
ratio, competitor title hits -> percentile performance score + absolute red flags
-> cut to after_2a, excluded list with reasons (recall audit input).
S2b: creator/detail (need_extra=True, same 0.1cr) for survivors -> bio, contacts
(never sent to LLM), new_followers spike flag, seller-status double check.
"""
from __future__ import annotations

from .. import planner
from ..evidence import record
from ..scoring import (ScoreCard, competitor_hits, content_score_text, niche_ratio,
                       normalize_video, percentile_rank, performance_metrics,
                       performance_score, red_flags, scoring_er, _to_int)


def _metric_val(m: dict, k: str):
    return scoring_er(m) if k == "median_er" else m.get(k, 0)
from . import s1_candidates

HARD_FLAGS = {"low_er", "no_video_data"}


def run(ctx) -> dict:
    pool = s1_candidates.load_pool(ctx)
    pool_by_id = {str(r["creator_id"]): r for r in pool}
    f = ctx.cfg.funnel
    camp = ctx.campaign
    keywords = camp.get("niche_keywords", [])
    competitors = camp.get("competitors", [])
    cat_ids = camp.get("category_ids", [])
    flags_cfg = ctx.cfg.raw["scoring"]["red_flags"]
    period_days = int(ctx.cfg.raw["run"].get("date_range_days", 30))
    io = int(ctx.cfg.raw["limits"]["io_concurrency"])

    # ---------- S2a ----------
    def worker_a(cid: str):
        params = ctx.kd.base_params(creator_id=cid, page_size=int(f.get("videos_fetch", 100)),
                                    page_number=1, sort_field={"field": "revenue", "type": "DESC"})
        data = ctx.kd.call("video/rank", params, "s2a")
        rows = data if isinstance(data, list) else data.get("list", [])
        videos = [normalize_video(r) for r in rows]
        followers = _to_int(pool_by_id[cid].get("creator_followers"))
        m = performance_metrics(videos, followers, period_days)
        return {"metrics": m, "videos": [v.model_dump() for v in videos],
                "followers": followers, "n_total": len(videos),
                "niche_ratio": niche_ratio(videos, keywords),
                "competitor_hits": competitor_hits(videos, [], competitors),
                "cache_key": ctx.kd.cache_key("video/rank", params)}

    ctx.runner.run("s2a", list(pool_by_id), worker_a, concurrency=io)
    res_a = ctx.runner.done_results("s2a")

    metric_keys = ["median_views", "median_er", "view_follower_ratio", "stability", "posts_per_week"]
    cap = int(ctx.cfg.raw["budget"].get("max_followers_assumed", 10**12))

    def _score_s2a(cur_pool_by_id: dict[str, dict], cur_res_a: dict[str, dict]):
        # pre-pass: hard red flags + budget-reach cap BEFORE percentiles,
        # so mega-influencers don't skew the pool-relative scoring of bookable KOCs
        pre = {}
        for cid, r in cur_res_a.items():
            flags = red_flags(r["metrics"], flags_cfg, r["competitor_hits"])
            hard = [fl for fl in flags if fl["flag"] in HARD_FLAGS]
            pre[cid] = (flags, hard, r["followers"] > cap)
        eligible = [cid for cid in cur_res_a if not pre[cid][1] and not pre[cid][2]
                    and cur_res_a[cid]["metrics"].get("n_videos", 0) > 0]
        pools = {k: [_metric_val(cur_res_a[cid]["metrics"], k) for cid in eligible] for k in metric_keys}
        cards: dict[str, ScoreCard] = {}
        for cid, r in cur_res_a.items():
            m = r["metrics"]
            flags, hard, over_cap = pre[cid]
            pcts = ({k: percentile_rank(_metric_val(m, k), pools[k]) for k in metric_keys}
                    if cid in eligible else {})
            perf, _ = performance_score(m, pcts, 25.0)
            content, cparts = content_score_text(r["niche_ratio"], m.get("ad_ratio", 0), r["competitor_hits"])
            card = ScoreCard(creator_id=cid, performance=perf, content=content,
                             content_measured_max=cparts["measured_max"], flags=flags)
            if hard:
                card.excluded = True
                card.exclude_reason = "; ".join(fl["detail"] for fl in hard)
            elif over_cap:
                card.excluded = True
                card.exclude_reason = (f"followers {r['followers']:,} > trần giả định {cap:,} — "
                                       "ngoài tầm ngân sách (giả định giá theo tier, xem README)")
            cards[cid] = card
            record(ctx.db, ctx.cfg.run_id, "s2a", "metric", f"api_cache:{r['cache_key']}",
                   m, creator_id=cid)
            record(ctx.db, ctx.cfg.run_id, "s2a", "niche_signal", f"api_cache:{r['cache_key']}",
                   {"niche_keyword_ratio": round(r["niche_ratio"], 3),
                    "competitor_title_hits": r["competitor_hits"],
                    "n_videos_sampled": r["n_total"]}, creator_id=cid)

        ranked = sorted((c for c in cards.values() if not c.excluded),
                        key=lambda c: (-c.internal_rank_score(), c.creator_id))
        kept = [c.creator_id for c in ranked[:int(f["after_2a"])]]
        excluded = [{"creator_id": c.creator_id,
                     "name": cur_pool_by_id.get(c.creator_id, {}).get("creator_nickname", ""),
                     "stage": "s2a", "hard": c.excluded,
                     "reason": c.exclude_reason or f"dưới ngưỡng cắt (điểm nội bộ {c.internal_rank_score():.3f}, giữ {len(kept)}/{len(cards)})",
                     "measured": c.measured, "measured_max": c.measured_max}
                    for c in cards.values() if c.creator_id not in kept]
        return cards, kept, excluded, pools

    cards, kept, excluded, pools = _score_s2a(pool_by_id, res_a)
    ctx.put_stage_result("s2a_cut", {"kept": kept, "excluded": excluded,
                                     "cards": {k: v.model_dump() for k, v in cards.items()},
                                     "pools": pools, "metric_keys": metric_keys})
    s2_decision = planner.decide_after_s2(ctx, kept, target_size=5)
    expanded_added = 0
    if s2_decision.action == "expand_candidates" and s2_decision.allowed and ctx.mode != "replay":
        extra_pool = s1_candidates.expand_pool(
            ctx, set(pool_by_id), extra_target=max(10, int(f.get("after_2a", 12))))
        if extra_pool:
            expanded_added = len(extra_pool)
            pool = list(pool) + extra_pool
            for r in extra_pool:
                pool_by_id[str(r["creator_id"])] = r
            s1_prev = ctx.stage_result("s1") or {}
            ctx.put_stage_result("s1", {**s1_prev, "pool": pool, "expanded": expanded_added})
            ctx.runner.run("s2a", [str(r["creator_id"]) for r in extra_pool], worker_a, concurrency=io)
            res_a = ctx.runner.done_results("s2a")
            cards, kept, excluded, pools = _score_s2a(pool_by_id, res_a)
            ctx.put_stage_result("s2a_cut", {"kept": kept, "excluded": excluded,
                                             "cards": {k: v.model_dump() for k, v in cards.items()},
                                             "pools": pools, "metric_keys": metric_keys})

    # ---------- S2b ----------
    def worker_b(cid: str):
        params = ctx.kd.base_params(creator_id=cid, need_extra=True,
                                    category_ids=cat_ids or None)
        d = ctx.kd.call("creator/detail", params, "s2b")
        return {"detail": d, "cache_key": ctx.kd.cache_key("creator/detail", params)}

    ctx.runner.run("s2b", kept, worker_b, concurrency=io)
    res_b = ctx.runner.done_results("s2b")

    final_kept, details = [], {}
    for cid in kept:
        rb = res_b.get(cid)
        card = cards[cid]
        if not rb:
            card.excluded = True
            card.exclude_reason = "creator/detail lỗi sau retry"
            excluded.append({"creator_id": cid, "name": pool_by_id.get(cid, {}).get("creator_nickname", ""),
                             "stage": "s2b", "hard": True, "reason": card.exclude_reason,
                             "measured": card.measured, "measured_max": card.measured_max})
            continue
        d = rb["detail"]
        if d.get("creator_status") == "BELONGED_TO_SELLER":
            card.excluded = True
            card.exclude_reason = "channel thuộc seller (không phải KOC độc lập)"
            excluded.append({"creator_id": cid, "name": d.get("creator_nickname", ""),
                             "stage": "s2b", "hard": True, "reason": card.exclude_reason,
                             "measured": card.measured, "measured_max": card.measured_max})
            continue
        followers = _to_int(d.get("creator_followers")) or res_a[cid]["followers"]
        new_f = _to_int(d.get("new_followers"))
        ratio = new_f / followers if followers else 0.0
        m = dict(res_a[cid]["metrics"])
        m["new_follower_ratio"] = round(ratio, 4)
        bio = str(d.get("creator_bio") or "")
        hits = sorted(set(res_a[cid]["competitor_hits"]) |
                      {c for c in competitors if c.lower() in bio.lower()})
        flags = red_flags(m, flags_cfg, hits)
        content, cparts = content_score_text(res_a[cid]["niche_ratio"], m.get("ad_ratio", 0), hits)
        card.flags = flags
        card.content = content
        card.content_measured_max = cparts["measured_max"]
        hard = [fl for fl in flags if fl["flag"] in HARD_FLAGS]
        if hard:
            card.excluded = True
            card.exclude_reason = "; ".join(fl["detail"] for fl in hard)
            excluded.append({"creator_id": cid, "name": d.get("creator_nickname", ""),
                             "stage": "s2b", "hard": True, "reason": card.exclude_reason,
                             "measured": card.measured, "measured_max": card.measured_max})
            continue
        # contacts kept locally for final CSV only — NEVER into LLM prompts/evidence
        details[cid] = {
            "creator_id": cid, "name": d.get("creator_nickname", ""),
            "handle": d.get("creator_handle", ""), "followers": followers,
            "bio": bio, "video_gpm": d.get("video_gpm"), "revenue": d.get("revenue"),
            "new_followers": new_f, "new_follower_ratio": round(ratio, 4),
            "top3_product_ids": d.get("top3_product_ids") or [],
            "region": d.get("creator_region", ""),
            "contacts": {k: v for k, v in d.items() if k.startswith("creator_contact_") and v},
            "cache_key": rb["cache_key"],
        }
        record(ctx.db, ctx.cfg.run_id, "s2b", "metric", f"api_cache:{rb['cache_key']}",
               {"bio": bio[:500], "video_gpm": d.get("video_gpm"),
                "new_follower_ratio": round(ratio, 4), "revenue": d.get("revenue"),
                "top3_product_ids": d.get("top3_product_ids") or []}, creator_id=cid)
        final_kept.append(cid)

    excluded.sort(key=lambda e: (e["stage"], e["creator_id"]))  # thứ tự ổn định cho audit sampling
    plan_dec_dict = s2_decision.model_dump()
    if expanded_added:
        plan_dec_dict["expanded_added"] = expanded_added
        plan_dec_dict["kept_after_expand"] = len(kept)
    result = {"kept": final_kept, "excluded": excluded,
              "cards": {k: v.model_dump() for k, v in cards.items()},
              "details": details,
              "plan_decision": plan_dec_dict}
    ctx.put_stage_result("s2", result)
    return result


def load(ctx) -> dict:
    r = ctx.stage_result("s2")
    return r if r else run(ctx)
