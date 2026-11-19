"""S1 — candidate acquisition: multi-slice creator/rank + round-robin dedupe.

Reasons: single revenue-sorted list biases to big sellers and misses nano KOC
(high engagement, low followers) — a dedicated nano slice + views/growth slices
keep the pool diverse (plan §13.4). creator_type=INDEPENDENT because spike
showed top-revenue rows are brand-owned stores, not KOCs.
"""
from __future__ import annotations


def run(ctx) -> list[dict]:
    f = ctx.cfg.funnel
    camp = ctx.campaign
    cat_ids = camp.get("category_ids", [])
    kw = (camp.get("niche_keywords") or ["kem chống nắng"])[0]
    items, slice_meta = [], []
    for i, sl in enumerate(f["slices"]):
        for p in range(1, int(sl.get("pages", 1)) + 1):
            item = f"slice{i}_page{p}"
            items.append(item)
            slice_meta.append((item, sl, p))

    def worker(item: str):
        sl, p = next((s, pp) for it, s, pp in slice_meta if it == item)
        params = ctx.kd.base_params(
            page_size=int(f.get("page_size", 100)), page_number=p,
            sort_field={"field": sl["sort"], "type": "DESC"},
            creator_type=f.get("creator_type", "INDEPENDENT"),
            followers_range=sl.get("followers_range"))
        if cat_ids:
            params["category_id_list"] = ",".join(cat_ids)
        else:
            params["keyword"] = kw
        data = ctx.kd.call("creator/rank", params, "s1")
        rows = data if isinstance(data, list) else data.get("list", [])
        return {"rows": rows, "sort": sl["sort"]}

    ctx.runner.run("s1", items, worker, concurrency=int(ctx.cfg.raw["limits"]["io_concurrency"]))
    results = ctx.runner.done_results("s1")

    # round-robin interleave across slices -> dedupe -> cap (diversity before truncation)
    lists = [results[it]["rows"] for it, _, _ in slice_meta if it in results]
    seen, pool = set(), []
    idx = 0
    while len(pool) < int(f["candidates"]) and any(lists):
        alive = []
        for lst in lists:
            if idx < len(lst):
                alive.append(lst)
                row = lst[idx]
                cid = str(row.get("creator_id", ""))
                if cid and cid not in seen:
                    seen.add(cid)
                    pool.append(row)
                    if len(pool) >= int(f["candidates"]):
                        break
        lists = alive
        idx += 1
        if not alive:
            break
    ctx.put_stage_result("s1", {"pool": pool, "n_slices": len(slice_meta)})
    return pool


def load_pool(ctx) -> list[dict]:
    r = ctx.stage_result("s1")
    if r:
        return r["pool"]
    return run(ctx)
