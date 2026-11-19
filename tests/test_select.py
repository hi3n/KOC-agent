from koc.select import Candidate, assign_tier, select_portfolio

TIERS = {"nano": [0, 10000], "micro": [10000, 50000], "mid": [50000, 150000],
         "anchor": [150000, 10**12]}
PRICES = {"nano": 2_000_000, "micro": 5_000_000, "mid": 6_000_000, "anchor": 7_000_000}
SLOTS = {"anchor": [1, 2], "mid": [2, 2], "nano": [1, 1], "micro": [0, 2]}


def _cands():
    spec = [("a1", 200000, 0.9), ("a2", 300000, 0.85), ("m1", 80000, 0.8),
            ("m2", 90000, 0.75), ("m3", 70000, 0.7), ("u1", 20000, 0.65),
            ("u2", 30000, 0.6), ("n1", 5000, 0.95)]
    out = []
    clusters = {"a1": "skincare_science", "a2": "skincare_science", "m1": "skincare_science",
                "m2": "skincare_science", "m3": "beauty_makeup", "u1": "skincare_science",
                "u2": "beauty_makeup", "n1": "lifestyle"}
    for cid, fol, score in spec:
        tier = assign_tier(fol, TIERS)
        out.append(Candidate(cid, cid, fol, tier, PRICES[tier], score, 1.0, clusters[cid]))
    return out


def test_feasible_respects_all_constraints():
    r = select_portfolio(_cands(), total_vnd=30_000_000, slots=SLOTS, size=5, max_per_cluster=2)
    assert r["feasible"]
    p = r["portfolios"][0]
    assert p["total_price_vnd"] <= 30_000_000
    tiers = [c.tier for c in p["members"]]
    assert 1 <= tiers.count("anchor") <= 2 and tiers.count("mid") == 2 and tiers.count("nano") == 1
    assert len(p["members"]) == 5
    clusters = [c.niche_cluster for c in p["members"]]
    assert max(clusters.count(x) for x in set(clusters)) <= 2
    assert len(r["backups"]) == 2
    assert abs(sum(p["price_ceiling_vnd"].values()) - 30_000_000) < 5
    assert p["max_price_scale"] >= 1.0
    assert "swap_options" in p
    assert r["relaxation_used"] is None  # pool đủ đa dạng, không phải nới


def test_infeasible_reports_reason():
    r = select_portfolio(_cands(), total_vnd=10_000_000, slots=SLOTS, size=5)
    assert not r["feasible"] and "không bộ 5" in r["infeasible_reason"]


def test_diversity_relaxation_is_explicit():
    cands = _cands()
    for c in cands:
        c.niche_cluster = "same"
    r = select_portfolio(cands, total_vnd=30_000_000, slots=SLOTS, size=5, max_per_cluster=2)
    assert r["feasible"] and r["relaxation_used"] and "diversity" in r["relaxation_used"]


def test_tier_boundaries():
    assert assign_tier(9999, TIERS) == "nano"
    assert assign_tier(10000, TIERS) == "micro"
    assert assign_tier(150000, TIERS) == "anchor"
