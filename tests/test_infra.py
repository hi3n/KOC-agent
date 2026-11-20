import json

import pytest
from pydantic import BaseModel

from koc.db import Database
from koc.kalodata import KalodataClient, WaitingKalodata
from koc.ledger import Ledger
from koc.llm import LLMClient, _cost, _strict_schema
from koc.config import LLMRole
from koc.runner import StageRunner


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "t.db")
    yield d
    d.close()


def test_runner_idempotent_and_retry(db):
    ledger = Ledger(db, "r1")
    runner = StageRunner(db, ledger, "r1")
    calls = []

    def worker(x):
        calls.append(x)
        if x == "bad" and len([c for c in calls if c == "bad"]) < 3:
            raise ValueError("boom")
        return {"v": x}

    s = runner.run("st", ["a", "bad"], worker, concurrency=2)
    assert s["done"] == 2 and calls.count("a") == 1 and calls.count("bad") == 3
    calls.clear()
    s2 = runner.run("st", ["a", "bad"], worker, concurrency=2)
    assert s2["done"] == 0 and not calls  # done items never re-run
    assert runner.done_results("st")["a"] == {"v": "a"}


def test_runner_waiting_backoff(db, monkeypatch):
    import koc.runner as runner_mod
    monkeypatch.setattr(runner_mod, "WAIT_BACKOFF_BASE", 0.02)
    runner = StageRunner(db, Ledger(db, "r1"), "r1")
    state = {"n": 0}

    def worker(x):
        state["n"] += 1
        if state["n"] == 1:
            raise WaitingKalodata(1054, "queued")
        return {}

    runner.run("st", ["v"], worker, concurrency=1)
    assert db.one("SELECT status FROM tasks WHERE entity_id='v'")["status"] == "done"


def test_stale_running_reset(db):
    runner = StageRunner(db, Ledger(db, "r1"), "r1")
    runner.ensure_tasks("st", ["x"])
    db.execute("UPDATE tasks SET status='running' WHERE entity_id='x'")
    assert db.reset_stale_running("r1") == 1
    assert db.one("SELECT status FROM tasks WHERE entity_id='x'")["status"] == "pending"


def test_kalodata_cache_pays_once(db, monkeypatch):
    ledger = Ledger(db, "r1")
    kd = KalodataClient(db, ledger, {"rate_per_10s": 1000}, "key", mode="rw",
                        fixtures_dir=db.conn.execute("PRAGMA database_list").fetchone()[2] + "_fx")
    n = {"fetch": 0}

    def fake_fetch(endpoint, params):
        n["fetch"] += 1
        return {"success": True, "data": {"ok": 1}, "cached": False}

    monkeypatch.setattr(kd, "_fetch", fake_fetch)
    a = kd.call("creator/detail", {"creator_id": "1"}, "s2b")
    b = kd.call("creator/detail", {"creator_id": "1"}, "s2b")
    assert a == b == {"ok": 1} and n["fetch"] == 1
    hits = db.one("SELECT SUM(cache_hit) h, SUM(credits) c FROM usage_ledger")
    assert hits["h"] == 1 and hits["c"] == 0.1
    kd.close()


class _Nested(BaseModel):
    quote: str
    start_s: float


class _Out(BaseModel):
    video_id: str
    score: float
    quotes: list[_Nested]


def test_strict_schema_inlines_defs():
    s = _strict_schema(_Out)
    assert "$defs" not in json.dumps(s)
    assert s["additionalProperties"] is False
    assert set(s["required"]) == {"video_id", "score", "quotes"}
    item = s["properties"]["quotes"]["items"]
    assert item["additionalProperties"] is False and set(item["required"]) == {"quote", "start_s"}


def test_cost_with_cache():
    prices = {"m": {"in": 4.0, "out": 20.0, "cache_read": 0.2}}
    c = _cost(prices, "m", 10000, 500, 8000)
    assert abs(c - (2000 * 4 + 8000 * 0.2 + 500 * 20) / 1e6) < 1e-9
    assert _cost(prices, "unknown", 1, 1, 0) is None


def test_llm_judgement_cache_hit_needs_no_key(db):
    ledger = Ledger(db, "r1")
    role = LLMRole(base_url="http://x", api_key="", model="m")
    llm = LLMClient(role, db, ledger, {}, "s3")
    out = _Out(video_id="v", score=0.5, quotes=[_Nested(quote="q", start_s=1.0)])
    from koc.config import canonical_hash
    sh = canonical_hash({"s": "sys", "c": "user", "schema": "_Out"})
    db.execute("INSERT INTO judgements (judgement_id, run_id, stage, entity_id, model,"
               " prompt_version, rubric_version, state_hash, output_json) VALUES"
               " ('j1','r1','s3','v','m','v1','v1',?,?)", (sh, out.model_dump_json()))
    got = llm.judge("sys", "user", _Out, "v")
    assert got.video_id == "v" and got.quotes[0].quote == "q"


def test_progress_logging_and_elapsed_timing(tmp_path, capsys):
    from koc.pipeline import create_ctx, fmt_elapsed, run_pipeline

    assert fmt_elapsed(4.2) == "4.2s"
    assert fmt_elapsed(311.2) == "5m 11.2s"
    assert fmt_elapsed(3735) == "1h 02m 15s"

    rep_dir = tmp_path / "out"
    ctx = create_ctx("briefs/sunscreen.txt", mode="replay", run_id="prog_test",
                     db_path=tmp_path / "koc.db", report_dir=rep_dir)
    try:
        run_pipeline(ctx, progress=True)
        out = capsys.readouterr().out
        assert "Bắt đầu chạy KOC Discovery" in out
        assert "[1/7]" in out and "[7/7]" in out
        assert "[OK]" in out
        assert "... s4_judge: 14/14 xong" in out
        assert ctx.last_elapsed_s > 0
        assert ctx.runner.on_progress is None
    finally:
        ctx.kd.close()
        ctx.db.close()
