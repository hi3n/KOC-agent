"""S1 — candidate acquisition: multi-slice creator/rank + round-robin dedupe.

Reasons: single revenue-sorted list biases to big sellers and misses nano KOC
(high engagement, low followers) — a dedicated nano slice + views/growth slices
keep the pool diverse (plan §13.4). creator_type=INDEPENDENT because spike
showed top-revenue rows are brand-owned stores, not KOCs.
"""
from __future__ import annotations


def _fetch_slices(ctx, stage_name: str, slice_meta: list[tuple[str, dict, int]]) -> dict[str, dict]:
    f = ctx.cfg.funnel
    camp = ctx.campaign
    cat_ids = camp.get("category_ids", [])
    kw = (camp.get("niche_keywords") or ["kem chống nắng"])[0]
    by_item = {it: (sl, p) for it, sl, p in slice_meta}

    def worker(item: str):
        sl, p = by_item[item]
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

    ctx.runner.run(stage_name, [it for it, _, _ in slice_meta], worker,
                   concurrency=int(ctx.cfg.raw["limits"]["io_concurrency"]))
    return ctx.runner.done_results(stage_name)


def _round_robin_dedupe(lists: list[list[dict]], limit: int,
                        existing_ids: set[str] | None = None) -> list[dict]:
    seen = set(existing_ids or ())
    pool: list[dict] = []
    idx = 0
    while len(pool) < limit and any(lists):
        alive = []
        for lst in lists:
            if idx < len(lst):
                alive.append(lst)
                row = lst[idx]
                cid = str(row.get("creator_id", ""))
                if cid and cid not in seen:
                    seen.add(cid)
                    pool.append(row)
                    if len(pool) >= limit:
                        break
        lists = alive
        idx += 1
        if not alive:
            break
    return pool


def run(ctx) -> list[dict]:
    f = ctx.cfg.funnel
    items_meta = [
        (f"slice{i}_page{p}", sl, p)
        for i, sl in enumerate(f["slices"])
        for p in range(1, int(sl.get("pages", 1)) + 1)
    ]
    results = _fetch_slices(ctx, "s1", items_meta)
    lists = [results[it]["rows"] for it, _, _ in items_meta if it in results]
    pool = _round_robin_dedupe(lists, int(f["candidates"]))
    ctx.put_stage_result("s1", {"pool": pool, "n_slices": len(items_meta)})
    return pool


def expand_pool(ctx, existing_ids: set[str], extra_target: int = 10) -> list[dict]:
    """Lấy thêm trang kế tiếp mỗi lát cắt khi Planner/Governor duyệt mở rộng ứng viên."""
    f = ctx.cfg.funnel
    items_meta = [
        (f"expand_slice{i}_page{int(sl.get('pages', 1)) + 1}", sl, int(sl.get("pages", 1)) + 1)
        for i, sl in enumerate(f["slices"])
    ]
    results = _fetch_slices(ctx, "s1_expand", items_meta)
    lists = [results[it]["rows"] for it, _, _ in items_meta if it in results]
    return _round_robin_dedupe(lists, extra_target, existing_ids=existing_ids)


def load_pool(ctx) -> list[dict]:
    r = ctx.stage_result("s1")
    if r:
        return r["pool"]
    return run(ctx)
