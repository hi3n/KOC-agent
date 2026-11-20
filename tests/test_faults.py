"""Fault injection tests: HTTP 429/503, truncated JSON, Kalodata 1053 missing video, expired signed URL."""
from __future__ import annotations

import json
import time
from types import SimpleNamespace

import httpx
import pytest
from pydantic import BaseModel

from koc.config import LLMRole
from koc.db import Database
from koc.kalodata import KalodataClient, VideoMissing
from koc.ledger import Ledger
from koc.llm import LLMClient
from koc.runner import StageRunner


@pytest.fixture
def db(tmp_path):
    d = Database(tmp_path / "faults.db")
    yield d
    d.close()


def test_fault_http_429_and_503_retry_succeeds(db, monkeypatch, tmp_path):
    monkeypatch.setattr(time, "sleep", lambda _: None)
    ledger = Ledger(db, "r_429")
    kd = KalodataClient(db, ledger, {"rate_per_10s": 1000}, "key", mode="rw", fixtures_dir=tmp_path / "fx")

    calls = {"n": 0}
    req = httpx.Request("POST", "https://www.kalodata.com/openapi/v1/tiktok/creator/detail")

    def fake_post(path, json=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429, request=req, json={"success": False, "message": "rate limited"})
        if calls["n"] == 2:
            return httpx.Response(503, request=req, json={"success": False, "message": "service unavailable"})
        return httpx.Response(200, request=req, json={"success": True, "data": {"ok": True}, "cached": False})

    monkeypatch.setattr(kd.http, "post", fake_post)
    out = kd.call("creator/detail", {"creator_id": "c1"}, "s2b")
    assert out == {"ok": True} and calls["n"] == 3
    kd.close()


class _MiniOut(BaseModel):
    video_id: str
    score: float


def test_fault_truncated_json_retries_then_recovers(db, monkeypatch):
    ledger = Ledger(db, "r_trunc")
    role = LLMRole(base_url="http://x", api_key="k", model="m1")
    llm = LLMClient(role, db, ledger, {}, "s4")

    attempts = {"n": 0}

    class _FakeCompletions:
        def create(self, **kw):
            attempts["n"] += 1
            content = (
                '{"video_id": "v1", "score":'
                if attempts["n"] == 1
                else '{"video_id": "v1", "score": 0.85}'
            )
            msg = SimpleNamespace(content=content)
            usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20, prompt_tokens_details=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=msg)], usage=usage)

    fake_sdk = SimpleNamespace(chat=SimpleNamespace(completions=_FakeCompletions()))
    monkeypatch.setattr(llm, "_sdk", lambda r: fake_sdk)

    res = llm.judge("sys", "user", _MiniOut, entity_id="v1")
    assert res.video_id == "v1" and res.score == 0.85 and attempts["n"] == 2
    notes = [r["note"] for r in db.query("SELECT note FROM usage_ledger WHERE run_id='r_trunc'")]
    assert any("invalid_attempt=1" in (n or "") for n in notes)


def test_fault_1053_video_missing_isolated_in_runner(db, monkeypatch, tmp_path):
    ledger = Ledger(db, "r_1053")
    kd = KalodataClient(db, ledger, {"rate_per_10s": 1000}, "key", mode="rw", fixtures_dir=tmp_path / "fx")
    req = httpx.Request("POST", "https://www.kalodata.com/openapi/v1/tiktok/video/url")
    monkeypatch.setattr(
        kd.http, "post",
        lambda path, json=None: httpx.Response(200, request=req, json={"success": False, "code": 1053, "message": "video missing"}),
    )

    with pytest.raises(VideoMissing):
        kd.call("video/url", {"video_id": "v_dead"}, "s4", ttl=0)

    runner = StageRunner(db, ledger, "r_1053")

    def worker(vid_id):
        if vid_id == "v_dead":
            kd.call("video/url", {"video_id": vid_id}, "s4", ttl=0)
        return {"ok": True}

    summary = runner.run("s4_media", ["v_dead", "v_ok"], worker, concurrency=2)
    assert summary["failed"] == 1 and summary["done"] == 1
    row = db.one("SELECT status, error FROM tasks WHERE run_id='r_1053' AND entity_id='v_dead'")
    assert row["status"] == "failed" and "1053" in row["error"]
    kd.close()


def test_fault_expired_video_url_refetches_once(db, monkeypatch, tmp_path):
    from koc.stages import s4_video
    from koc import video as vid_mod

    run_dir = tmp_path / "runs" / "r_exp"
    run_dir.mkdir(parents=True)
    db.execute("INSERT INTO runs (run_id, config_json, config_hash) VALUES ('r_exp', '{}', 'h')")
    db.execute("INSERT INTO tasks (run_id, stage, entity_id, status, result_json) VALUES ('r_exp','s2a','c1','done',?)",
               (json.dumps({"videos": [{"video_id": "v1", "title": "kem chong nang", "revenue": 100, "published": "2026-11-18"}],
                            "metrics": {"ad_ratio": 0.1}, "niche_ratio": 1.0}),))
    db.execute("INSERT INTO tasks (run_id, stage, entity_id, status, result_json) VALUES ('r_exp','s2','pool','done',?)",
               (json.dumps({"kept": ["c1"], "excluded": [], "cards": {"c1": {"creator_id": "c1", "performance": 15, "content": 15, "content_measured_max": 16}}, "details": {"c1": {"name": "C1"}}}),))
    db.execute("INSERT INTO tasks (run_id, stage, entity_id, status, result_json) VALUES ('r_exp','s3','pool','done',?)",
               (json.dumps({"kept": ["c1"], "excluded_cut": [], "judgements": {"c1": {"niche_fit": 0.8}}, "cards": {"c1": {"creator_id": "c1", "performance": 15, "content": 20, "content_measured_max": 21}}}),))

    from koc.pipeline import Ctx
    from koc.config import build_config
    cfg = build_config(overrides={"funnel": {"videos_per_creator": 1, "video_roles": ["top_selling"]}, "limits": {"credit_budget": 10.0}})
    cfg.run_id = "r_exp"
    kd = KalodataClient(db, Ledger(db, "r_exp"), cfg.kalodata, "k", mode="rw", fixtures_dir=tmp_path / "fx")
    ctx = Ctx(cfg, db, Ledger(db, "r_exp"), kd, mode="rw", run_dir=run_dir, report_dir=run_dir)

    url_calls = {"n": 0}
    dl_calls = {"n": 0}
    monkeypatch.setattr(kd, "call", lambda ep, params, stage, ttl=None: (url_calls.__setitem__("n", url_calls["n"] + 1) or {"video_url": f"https://cdn.example/{url_calls['n']}.mp4"}))

    def fake_download(url, dest):
        dl_calls["n"] += 1
        if dl_calls["n"] == 1:
            req = httpx.Request("GET", url)
            raise httpx.HTTPStatusError("403 expired", request=req, response=httpx.Response(403, request=req))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mp4bytes")
        return dest, "hash123", 8

    monkeypatch.setattr(vid_mod, "download", fake_download)
    monkeypatch.setattr(vid_mod, "probe_duration", lambda p: 15.0)
    monkeypatch.setattr(vid_mod, "extract_frames", lambda *a, **k: [])
    monkeypatch.setattr(vid_mod, "transcribe", lambda *a, **k: {"text": "test", "segments": []})
    monkeypatch.setattr(vid_mod, "file_hash", lambda p: "hash123")
    monkeypatch.setattr(ctx, "llm", lambda role, stage: SimpleNamespace(
        replay=True, chain=[],
        judge=lambda *a, **k: SimpleNamespace(
            visual_quality=0.8, demo_quality=0.8, hook_strength=0.8, audio_clarity=0.8,
            knowledge_accuracy=0.8, knowledge_issues=[], exaggerated_claims=[],
            ad_disclosure_ok=True, transcript_quotes=[], frame_observations=["ok"],
            style_notes="ok", confidence=0.9,
            model_dump=lambda: {"visual_quality": 0.8, "demo_quality": 0.8, "hook_strength": 0.8,
                                "audio_clarity": 0.8, "knowledge_accuracy": 0.8, "confidence": 0.9},
        ),
    ))

    out = s4_video.run(ctx)
    assert url_calls["n"] == 2 and dl_calls["n"] == 2
    assert len(out["video_judgements"]) == 1
    kd.close()
