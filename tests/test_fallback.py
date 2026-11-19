"""Bounded failover: chain per-role, ledgered, degrade-don't-stop."""
import pytest
from pydantic import BaseModel

from koc.config import LLMRole
from koc.db import Database
from koc.evidence import audit_numeric_claims, record, validate_reason
from koc.ledger import Ledger
from koc.llm import LLMClient, LLMUnavailable


class _Out(BaseModel):
    video_id: str
    score: float


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def _client(db, fallbacks):
    role = LLMRole(model="m1", api_key="k", base_url="http://x", fallbacks=fallbacks)
    return LLMClient(role, db, Ledger(db, "r"), {}, "s3")


def test_chain_falls_over_and_ledgers(db, monkeypatch):
    llm = _client(db, [LLMRole(model="m2", api_key="k", base_url="http://y")])

    def live(member, *a, **k):
        if member.model == "m1":
            raise LLMUnavailable("AuthenticationError: bad key")
        return _Out(video_id="v", score=1.0)

    monkeypatch.setattr(llm, "_judge_live", live)
    got = llm.judge("sys", "user", _Out, "e")
    assert got.video_id == "v"
    notes = [r["note"] for r in db.query("SELECT note FROM usage_ledger")]
    assert any("UNAVAILABLE m1" in n and "fallback m2" in n for n in notes)


def test_all_fail_raises_unavailable(db, monkeypatch):
    llm = _client(db, [LLMRole(model="m2", api_key="k")])
    monkeypatch.setattr(llm, "_judge_live",
                        lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("down")))
    with pytest.raises(LLMUnavailable):
        llm.judge("sys", "user", _Out, "e")


def test_missing_key_is_unavailable_not_crash(db):
    llm = LLMClient(LLMRole(model="m", api_key=""), db, Ledger(db, "r"), {}, "s3")
    with pytest.raises(LLMUnavailable):
        llm.judge("sys", "user", _Out, "e")


def test_cache_hit_skips_chain_entirely(db, monkeypatch):
    from koc.config import canonical_hash
    llm = _client(db, [])
    sh = canonical_hash({"s": "sys", "c": "user", "schema": "_Out"})
    db.execute("INSERT INTO judgements (judgement_id, run_id, stage, entity_id, model,"
               " prompt_version, rubric_version, state_hash, output_json) VALUES"
               " ('j','r','s3','e','m1','v1','v1',?,?)",
               (sh, _Out(video_id="cached", score=0.5).model_dump_json()))
    monkeypatch.setattr(llm, "_judge_live",
                        lambda *a, **k: pytest.fail("không được gọi live khi cache hit"))
    assert llm.judge("sys", "user", _Out, "e").video_id == "cached"


def test_replay_matches_bundle_across_model_prefix(db):
    """Offline replay phải khớp judgement cache kể cả khi người chấm không có .env
    (model mặc định claude-sonnet-5-5 khác với ag/claude-sonnet-5-5 trong bundle)."""
    from koc.config import canonical_hash
    sh = canonical_hash({"s": "sys", "c": "user", "schema": "_Out"})
    db.execute("INSERT INTO judgements (judgement_id, run_id, stage, entity_id, model,"
               " prompt_version, rubric_version, state_hash, output_json) VALUES"
               " ('j','r','s3','e','ag/claude-sonnet-5-5','v1','v1',?,?)",
               (sh, _Out(video_id="from_bundle", score=0.9).model_dump_json()))
    llm = LLMClient(LLMRole(model="claude-sonnet-5-5", api_key=""), db, Ledger(db, "r"), {}, "s3", replay=True)
    assert llm.judge("sys", "user", _Out, "e").video_id == "from_bundle"


def test_s0_degrades_without_llm(tmp_path, monkeypatch):
    from koc.pipeline import create_ctx
    from koc.stages import s0_brief
    monkeypatch.setattr(LLMClient, "judge",
                        lambda *a, **k: (_ for _ in ()).throw(LLMUnavailable("test: no provider")))
    ctx = create_ctx("briefs/sunscreen.txt", mode="replay", run_id="t_s0deg",
                     db_path=tmp_path / "d.db")
    a = s0_brief.run(ctx)
    assert "DEGRADED" in a.rationale
    assert "601602" in a.category_ids  # keyword match trên cây danh mục thật từ fixture
    assert a.budget_vnd == 30_000_000
    ev = ctx.db.query("SELECT * FROM evidence WHERE kind='degraded'")
    assert ev, "phải ghi evidence degraded"
    ctx.kd.close()
    ctx.db.close()


def test_evidence_validator(db):
    eid = record(db, "r", "s2a", "metric", "api_cache:k", {"median_views": 1000}, creator_id="c1")
    db.execute("INSERT INTO videos (run_id, video_id, creator_id, status) VALUES ('r','v1','c1','processed')")
    good = {"creator_id": "c1", "strengths": [{"claim": "view 1000", "evidence_ids": [eid]}],
            "videos_watched": {"seen": 1, "total": 10}}
    assert validate_reason(db, "r", good) == []
    bad = {"creator_id": "c1", "strengths": [{"claim": "bịa", "evidence_ids": ["ev_fake"]}],
           "videos_watched": {"seen": 5, "total": 10}}
    issues = validate_reason(db, "r", bad)
    assert len(issues) == 2  # evidence giả + seen lệch số thật
    no_ev = {"creator_id": "c1", "strengths": [{"claim": "không nguồn", "evidence_ids": []}],
             "videos_watched": {"seen": 1, "total": 10}}
    assert validate_reason(db, "r", no_ev)


def test_audit_numeric_claims_dry_run(db):
    eid1 = record(db, "r", "s2a", "metric", "api_cache:k1",
                  {"median_views": 3153, "ad_ratio": 0.256}, creator_id="c1")
    record(db, "r", "s2b", "metric", "api_cache:k2",
           {"video_gpm": 558148.92}, creator_id="c1")
    reasons = [{
        "creator_id": "c1",
        "strengths": [
            {"claim": "median_views 3153, ad_ratio 0.256, GPM 558148.92, bịa 99999",
             "evidence_ids": [eid1]},
        ],
    }]
    res = audit_numeric_claims(db, "r", reasons)
    assert res["total_numbers"] == 4
    assert res["in_cited_evidence"] == 2          # 3153, 0.256
    assert res["in_creator_other_evidence"] == 1  # 558148.92 (in k2)
    assert len(res["unmatched"]) == 1 and res["unmatched"][0]["number"] == 99999.0


def test_plan_videos_niche_first_and_preserves_existing(db):
    import random
    from types import SimpleNamespace
    from koc.stages.s4_video import _plan_videos

    ctx = SimpleNamespace(
        db=db,
        cfg=SimpleNamespace(
            run_id="r_plan",
            funnel={"video_roles": ["top_selling", "latest"], "videos_per_creator": 2},
        ),
        campaign={"niche_keywords": ["kem chống nắng", "spf"]},
    )
    res_a = {
        "c1": {
            "videos": [
                {"video_id": "v_dress", "title": "try-on váy dự tiệc", "revenue": 900_000, "published": "2026-11-18"},
                {"video_id": "v_sun1", "title": "review kem chống nắng SPF50", "revenue": 100_000, "published": "2026-11-10"},
                {"video_id": "v_sun2", "title": "kem chống nắng kiềm dầu", "revenue": 50_000, "published": "2026-11-15"},
            ]
        }
    }
    # 1. Run mới (chưa có video processed): ưu tiên video khớp từ khóa ngách dù revenue thấp hơn váy
    planned = _plan_videos(ctx, ["c1"], res_a, random.Random(42))
    assert [p["video_id"] for p in planned] == ["v_sun1", "v_sun2"]

    # 2. Run đã có video processed (replay/resume): giữ nguyên để không phá cache
    db.execute("INSERT INTO videos (run_id, video_id, creator_id, role, file_hash, status)"
               " VALUES ('r_plan','v_dress','c1','top_selling','h1','processed'),"
               " ('r_plan','v_sun1','c1','latest','h2','processed')")
    planned_cached = _plan_videos(ctx, ["c1"], res_a, random.Random(42))
    assert {p["video_id"] for p in planned_cached} == {"v_dress", "v_sun1"}
