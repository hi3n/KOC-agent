"""S5 portfolio selection — exhaustive combinatorics in code, never LLM.

Reasons (ARCHITECTURE.md D13/D14):
- Hard constraints (budget <= 30M, slots, diversity) must hold with certainty;
  an LLM cannot guarantee them. C(15,5)=3003 combos enumerate in milliseconds.
- Deterministic + explainable: top-3 portfolios, per-member swap delta,
  max_price_scale, per-KOC price ceiling, backups.
- Price is an explicit assumption (tier table), kept OUT of quality scores so a
  rough guess never distorts ranking. Unknown real prices become action rules:
  quote above ceiling -> switch to that slot's backup.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass


@dataclass
class Candidate:
    creator_id: str
    name: str
    followers: int
    tier: str                      # nano | micro | mid | anchor
    price_vnd: float               # assumed, tier table x price_scale
    rank_score: float              # internal normalized score (coverage-penalized)
    coverage: float                # measured_max / 65
    niche_cluster: str = "other"
    measured: float = 0.0
    measured_max: float = 0.0


def assign_tier(followers: int, tier_followers: dict) -> str:
    for tier in ("nano", "micro", "mid", "anchor"):
        lo, hi = tier_followers.get(tier, [0, 10**12])
        if lo <= followers < hi:
            return tier
    return "anchor"


def price_candidates(cands: list[Candidate], price_tiers: dict, scale: float = 1.0) -> list[Candidate]:
    for c in cands:
        c.price_vnd = price_tiers.get(c.tier, 5_000_000) * scale
    return cands


def _slot_ok(combo: list[Candidate], slots: dict) -> bool:
    counts: dict[str, int] = {}
    for c in combo:
        counts[c.tier] = counts.get(c.tier, 0) + 1
    for tier, bound in slots.items():
        lo, hi = (bound if isinstance(bound, (list, tuple)) else (bound, bound))
        if not (lo <= counts.get(tier, 0) <= hi):
            return False
    return True


def _diverse_ok(combo: list[Candidate], max_per_cluster: int) -> bool:
    counts: dict[str, int] = {}
    for c in combo:
        counts[c.niche_cluster] = counts.get(c.niche_cluster, 0) + 1
        if counts[c.niche_cluster] > max_per_cluster:
            return False
    return True


TIER_RANK = {"anchor": 0, "mid": 1, "micro": 2, "nano": 3}


def select_portfolio(cands: list[Candidate], *, total_vnd: float, slots: dict,
                     size: int = 5, max_per_cluster: int = 2,
                     top_n: int = 3) -> dict:
    """Returns {feasible, portfolios:[{members, total_price, total_score,
    max_price_scale, ceilings}], infeasible_reason, relaxation_used}."""
    priced = [c for c in cands if c.price_vnd > 0]
    if len(priced) < size:
        return {"feasible": False, "portfolios": [],
                "infeasible_reason": f"chỉ có {len(priced)} ứng viên, cần {size}"}

    def evaluate(relax_diversity: bool = False, relax_slots: bool = False):
        results = []
        for combo in itertools.combinations(priced, size):
            total_price = sum(c.price_vnd for c in combo)
            if total_price > total_vnd:
                continue
            if not relax_slots and not _slot_ok(list(combo), slots):
                continue
            if not relax_diversity and not _diverse_ok(list(combo), max_per_cluster):
                continue
            score = sum(c.rank_score for c in combo)
            results.append((score, total_price, combo))
        # tie-break đủ mọi cấp: điểm → giá → tập id — không phụ thuộc thứ tự input
        results.sort(key=lambda r: (-r[0], r[1], tuple(sorted(c.creator_id for c in r[2]))))
        return results

    results = evaluate()
    relaxation = None
    if not results:
        results = evaluate(relax_diversity=True)
        relaxation = "diversity (không đủ ứng viên khác cụm)"
    if not results:
        results = evaluate(relax_diversity=True, relax_slots=True)
        relaxation = "diversity + slots (chỉ giữ ràng buộc ngân sách)"
    if not results:
        cheapest = sorted(c.price_vnd for c in priced)[:size]
        return {"feasible": False, "portfolios": [],
                "infeasible_reason": (
                    f"không bộ {size} nào <= {total_vnd:,.0f} VNĐ; "
                    f"rẻ nhất có thể: {sum(cheapest):,.0f} VNĐ. "
                    "Giảm slot hoặc tăng ngân sách — hệ thống không âm thầm vượt."),
                "relaxation_used": None}

    portfolios = []
    for score, total_price, combo in results[:top_n]:
        # thứ tự thành viên canonical (tier → id): CSV/report/hash ổn định giữa các run
        members = sorted(combo, key=lambda c: (TIER_RANK.get(c.tier, 9), c.creator_id))
        ceilings = {c.creator_id: round(total_vnd * c.price_vnd / total_price) for c in members}
        portfolios.append({
            "members": members,
            "total_price_vnd": round(total_price),
            "total_score": round(score, 4),
            "max_price_scale": round(total_vnd / total_price, 4) if total_price else None,
            "price_ceiling_vnd": ceilings,
        })

    # swap deltas for best portfolio: best feasible replacement per member
    best = portfolios[0]
    member_ids = {c.creator_id for c in best["members"]}
    outsiders = [c for c in priced if c.creator_id not in member_ids]
    swaps = {}
    for m in best["members"]:
        best_swap = None
        for o in outsiders:
            trial = [o if c.creator_id == m.creator_id else c for c in best["members"]]
            if sum(c.price_vnd for c in trial) > total_vnd:
                continue
            if not _slot_ok(trial, slots) or not _diverse_ok(trial, max_per_cluster):
                continue
            delta = o.rank_score - m.rank_score
            if best_swap is None or delta > best_swap["score_delta"]:
                best_swap = {"replace_with": o.creator_id, "name": o.name,
                             "score_delta": round(delta, 4),
                             "price_delta_vnd": round(o.price_vnd - m.price_vnd)}
        swaps[m.creator_id] = best_swap
    best["swap_options"] = swaps

    # backups: best outsiders, tie-break id cho thứ tự ổn định
    backups = sorted(outsiders, key=lambda c: (-c.rank_score, c.creator_id))[:2]
    return {"feasible": True, "portfolios": portfolios, "backups": backups,
            "infeasible_reason": None, "relaxation_used": relaxation}


def price_sensitivity(cands: list[Candidate], *, total_vnd: float, slots: dict,
                      price_tiers: dict, scenarios: list[float], **kw) -> list[dict]:
    out = []
    for scale in scenarios:
        priced = price_candidates([Candidate(**{k: getattr(c, k) for k in
                                  ("creator_id", "name", "followers", "tier", "price_vnd",
                                   "rank_score", "coverage", "niche_cluster", "measured",
                                   "measured_max")}) for c in cands], price_tiers, scale)
        r = select_portfolio(priced, total_vnd=total_vnd, slots=slots, **kw)
        out.append({"price_scale": scale, "feasible": r["feasible"],
                    "best_total_vnd": r["portfolios"][0]["total_price_vnd"] if r["portfolios"] else None,
                    "best_members": [c.creator_id for c in r["portfolios"][0]["members"]] if r["portfolios"] else [],
                    "max_price_scale": r["portfolios"][0]["max_price_scale"] if r["portfolios"] else None,
                    "infeasible_reason": r.get("infeasible_reason")})
    return out
