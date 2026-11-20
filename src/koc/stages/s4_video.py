"""S4 — representative video analysis (the expensive tier, top-K only).

Plan (seeded): top_selling + latest per creator (random 3rd = config knob).
Media task: video/url (ttl=0, signed link expires in 5 min) -> immediate download
-> hash -> ffmpeg frames (2 hook + uniform) -> faster-whisper transcript.
Judge task: frames + timestamped transcript -> multimodal LLM, closed schema,
explicit cache_key (file_hash+transcript) so offline replay hits judgement cache
without re-rendering base64. Evidence recorded per quote/observation/score.
Credit guard: if remaining budget can't cover planned URLs, drop 'latest' roles
first (degrade, don't stop) — event logged into result + report.
1053 missing video -> replacement from cached rank list, no extra API discovery.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path

from ..config import canonical_hash
from ..evidence import record
from ..prompts import S4_SYSTEM, VideoJudgement, PROMPT_VERSION
from ..scoring import ScoreCard, content_score_text, visual_score
from .. import video as vid
from . import s3_screen


_BLIND_PHRASES = ("không kèm khung hình", "không có khung hình", "không nhận được khung hình",
                  "không thấy ảnh", "input không có ảnh")


def _is_blind_obs(obs_list: list[str]) -> bool:
    txt = " ".join(obs_list or []).lower()
    return any(p in txt for p in _BLIND_PHRASES)


def _niche_hits(title: str, keywords: list[str]) -> int:
    if not title or not keywords:
        return 0
    t = title.lower()
    return sum(1 for k in keywords if k.lower() in t)


def _plan_videos(ctx, kept, res_a, rng):
    """Chọn video đại diện cho mỗi creator.
    - Nếu run/bundle đã có video đã tải/xử lý (file_hash IS NOT NULL) của creator đó,
      giữ nguyên để bảo toàn cache/determinism khi resume hoặc replay offline.
    - Với run mới, ưu tiên video có tiêu đề khớp niche_keywords trước (tie-break tất định:
      số keyword khớp → revenue/publish_date → video_id), rồi mới fallback sang video chung."""
    f = ctx.cfg.funnel
    roles = list(f.get("video_roles", ["top_selling", "latest"]))
    n_per = int(f.get("videos_per_creator", 2))
    keywords = ctx.campaign.get("niche_keywords", [])
    existing_rows = ctx.db.query(
        "SELECT video_id, creator_id, role FROM videos WHERE run_id=? AND file_hash IS NOT NULL"
        " AND role NOT LIKE '%_replacement'",
        (ctx.cfg.run_id,))
    existing_by_cid: dict[str, list[dict]] = {}
    for r in existing_rows:
        existing_by_cid.setdefault(r["creator_id"], []).append(dict(r))

    planned = []
    for cid in kept:
        if len(existing_by_cid.get(cid, [])) >= n_per:
            planned += existing_by_cid[cid][:n_per]
            continue
        videos = res_a.get(cid, {}).get("videos", [])
        if not videos:
            continue
        by_rev = sorted(videos, key=lambda v: (
            -_niche_hits(v.get("title", ""), keywords),
            -(v.get("revenue") or 0),
            v.get("video_id", ""),
        ))
        by_date = sorted((v for v in videos if v.get("published")), key=lambda v: (
            _niche_hits(v.get("title", ""), keywords),
            v["published"],
            v.get("video_id", ""),
        ), reverse=True)
        picked, picked_ids = [], set()
        for role in roles[:n_per]:
            cand = None
            if role == "top_selling":
                cand = next((v for v in by_rev if v["video_id"] not in picked_ids), None)
            elif role == "latest":
                cand = next((v for v in by_date if v["video_id"] not in picked_ids), None)
            elif role == "random":
                rest = [v for v in videos if v["video_id"] not in picked_ids]
                cand = rng.choice(rest) if rest else None
            if cand:
                picked.append({"video_id": cand["video_id"], "creator_id": cid, "role": role})
                picked_ids.add(cand["video_id"])
        planned += picked
    return planned


def run(ctx) -> dict:
    s3 = s3_screen.load(ctx)
    res_a = ctx.runner.done_results("s2a")
    cards = {k: ScoreCard(**v) for k, v in s3["cards"].items()}
    kept = s3["kept"]
    rng = random.Random(ctx.cfg.seed)
    limits = ctx.cfg.raw["limits"]
    run_dir = ctx.run_dir

    planned = _plan_videos(ctx, kept, res_a, rng)
    events = []
    # credit guard: degrade video count instead of stopping (plan §5).
    # Chỉ tính video CHƯA processed — video đã xong đã trả tiền rồi (ledger counted),
    # warm re-plan/resume không được trigger guard oan (bug 19/11: warm thấy 0.2cr
    # và báo "bỏ 7 video" dù 14 video đã analyze xong).
    done_ids = {r["video_id"] for r in ctx.db.query(
        "SELECT video_id FROM videos WHERE run_id=? AND status IN ('processed','processed_local')",
        (ctx.cfg.run_id,))}
    new_needed = [p for p in planned if p["video_id"] not in done_ids]
    available = float(limits["credit_budget"]) - ctx.ledger.credits_used()
    cost_needed = 0.5 * len(new_needed)
    if cost_needed > available:
        keep_ids = {p["video_id"] for p in new_needed if p["role"] == "top_selling"} | (done_ids & {p["video_id"] for p in planned})
        dropped = [p for p in planned if p["video_id"] not in keep_ids]
        planned = [p for p in planned if p["video_id"] in keep_ids]
        events.append(f"credit guard: còn {available:.1f}cr < cần {cost_needed:.1f}cr cho {len(new_needed)} video MỚI → bỏ {len(dropped)} video 'latest', giữ top_selling + video đã xong")
    with ctx.db.transaction() as conn:
        for p in planned:
            conn.execute(
                "INSERT OR IGNORE INTO videos (run_id, video_id, creator_id, role, status)"
                " VALUES (?,?,?,?,'pending')",
                (ctx.cfg.run_id, p["video_id"], p["creator_id"], p["role"]))

    media_dir, frames_dir, trans_dir = run_dir / "media", run_dir / "frames", run_dir / "transcripts"

    def media_worker(video_id: str):
        vrow = ctx.db.one("SELECT * FROM videos WHERE run_id=? AND video_id=?",
                          (ctx.cfg.run_id, video_id))
        mp4 = media_dir / f"{video_id}.mp4"
        if ctx.mode == "replay":
            if vrow["file_hash"]:
                return {"replay": True, "file_hash": vrow["file_hash"]}
            raise RuntimeError("replay: thiếu file_hash trong bundle, không dựng được cache key")
        # resume: file intact -> skip re-download (expired URL would cost 0.5cr again)
        if mp4.exists() and vrow["file_hash"] and vid.file_hash(mp4) == vrow["file_hash"]:
            fh, size = vrow["file_hash"], mp4.stat().st_size
        else:
            vu = ctx.kd.call("video/url", {"video_id": video_id}, "s4", ttl=0)
            url = vu.get("video_url") or vu.get("url")
            if not url:
                raise RuntimeError(f"video/url không trả link: {vu}")
            _, fh, size = vid.download(url, mp4)
        duration = vrow["duration_s"] or vid.probe_duration(mp4)
        vcfg = ctx.cfg.raw["video"]
        frame_paths = vid.extract_frames(
            mp4, frames_dir / video_id, duration,
            frames=int(vcfg["frames"]), hook_frames=int(vcfg["hook_frames"]),
            hook_seconds=float(vcfg["hook_seconds"]), width=int(vcfg["frame_width"]),
            quality=int(vcfg["jpeg_quality"]), cap_s=float(ctx.cfg.raw["asr"]["max_video_seconds"]))
        transcript, asr_ms, asr_err = None, 0, None
        tpath = trans_dir / f"{video_id}.json"
        try:
            t0 = time.perf_counter()
            transcript = vid.transcribe(mp4, tpath, ctx.cfg.raw["asr"], duration)
            asr_ms = int((time.perf_counter() - t0) * 1000)
            ctx.ledger.log("asr", "s4", entity_id=video_id, latency_ms=asr_ms,
                           note=ctx.cfg.raw["asr"]["model"])
        except vid.ASRUnavailable as e:
            asr_err = str(e)
            ctx.ledger.log("asr", "s4", entity_id=video_id, note=f"unavailable: {asr_err}")
        with ctx.db.transaction() as conn:
            conn.execute(
                "UPDATE videos SET file_path=?, file_hash=?, bytes=?, duration_s=?,"
                " transcript_path=?, frames_json=?, status='processed_local'"
                " WHERE run_id=? AND video_id=?",
                (str(mp4), fh, size, duration, str(tpath) if transcript else None,
                 json.dumps([str(p) for p in frame_paths]), ctx.cfg.run_id, video_id))
        return {"file_hash": fh, "duration_s": duration, "asr_ms": asr_ms,
                "asr_error": asr_err, "n_frames": len(frame_paths)}

    ctx.runner.run("s4_media", [p["video_id"] for p in planned], media_worker,
                   concurrency=int(limits["io_concurrency"]))

    def judge_worker(video_id: str):
        vrow = ctx.db.one("SELECT * FROM videos WHERE run_id=? AND video_id=?",
                          (ctx.cfg.run_id, video_id))
        if not vrow or not vrow["file_hash"]:
            raise RuntimeError(f"media chưa sẵn sàng cho {video_id}")
        cid = vrow["creator_id"]
        meta = next((v for v in res_a.get(cid, {}).get("videos", [])
                     if v["video_id"] == video_id), {})
        transcript = None
        if vrow["transcript_path"] and Path(vrow["transcript_path"]).exists():
            transcript = json.loads(Path(vrow["transcript_path"]).read_text(encoding="utf-8"))
        ttext = transcript["text"][:4000] if transcript else ""
        thash = canonical_hash(ttext)[:12]
        text = (
            f"Video {video_id} của creator {cid} (vai trò mẫu: {vrow['role']}).\n"
            f"Tiêu đề: {meta.get('title', '')[:300]}\n"
            f"Đăng: {meta.get('published', '?')} | thời lượng: {vrow['duration_s']:.0f}s | "
            f"views: {meta.get('views', 0)} | like: {meta.get('likes', 0)} | "
            f"comment: {meta.get('comments', 0)} | share: {meta.get('shares', 0)} | "
            f"quảng cáo: {bool(meta.get('is_ad'))}\n"
            f"Khung hình theo thứ tự thời gian (2 khung đầu trong 3s mở đầu).\n"
            + (f"<transcript>\n" + "\n".join(
                f"[{s['start']:.1f}-{s['end']:.1f}] {s['text']}"
                for s in transcript["segments"][:80]) + "\n</transcript>"
               if transcript else
               "[TRANSCRIPT KHÔNG KHẢ DỤNG — ASR lỗi/không nạp được. Chỉ chấm phần hình ảnh; "
               "audio_clarity và knowledge_accuracy đặt 0.5 trung tính, confidence giảm.]"))
        content = [{"type": "text", "text": text}]
        frame_paths = [Path(p) for p in json.loads(vrow["frames_json"] or "[]") if Path(p).exists()]
        content += vid.frames_to_blocks(frame_paths)
        cache_key = f"s4:{PROMPT_VERSION}:{video_id}:{vrow['file_hash']}:{thash}"
        v_llm = ctx.llm("video", "s4")
        j = v_llm.judge(S4_SYSTEM, content, VideoJudgement,
                        entity_id=video_id, cache_key=cache_key)
        # Agentic Self-Correction: nếu đã gửi frame_paths thật nhưng gateway của model
        # chính làm rơi block ảnh (model báo "không có khung hình") và có cấu hình
        # vision fallback trong chain → tự động chuyển sang model vision dự phòng.
        if frame_paths and _is_blind_obs(j.frame_observations) and not v_llm.replay and len(v_llm.chain) > 1:
            fb_role = v_llm.chain[1]
            v_llm.ledger.log("llm", "s4", entity_id=video_id,
                             note=f"AGENT_VISION_REROUTE {v_llm.role.model} (blind gateway) → {fb_role.model}")
            j = v_llm._judge_live(fb_role, S4_SYSTEM, content, VideoJudgement,
                                  video_id, cache_key, "v1", 3)
        fh = vrow["file_hash"]
        for q in j.transcript_quotes:
            record(ctx.db, ctx.cfg.run_id, "s4", "transcript_quote",
                   f"{fh}:{q.start_s}-{q.end_s}", q.model_dump(), creator_id=cid, video_id=video_id)
        if j.frame_observations:
            record(ctx.db, ctx.cfg.run_id, "s4", "frame_obs", f"{fh}:frames",
                   {"observations": j.frame_observations, "style_notes": j.style_notes},
                   creator_id=cid, video_id=video_id)
        record(ctx.db, ctx.cfg.run_id, "s4", "metric", f"judgement:s4:{video_id}",
               {k: getattr(j, k) for k in ("visual_quality", "demo_quality", "hook_strength",
                                           "audio_clarity", "knowledge_accuracy", "confidence")}
               | {"knowledge_issues": j.knowledge_issues,
                  "exaggerated_claims": j.exaggerated_claims,
                  "ad_disclosure_ok": j.ad_disclosure_ok},
               creator_id=cid, video_id=video_id)
        ctx.db.execute("UPDATE videos SET status='processed' WHERE run_id=? AND video_id=?",
                       (ctx.cfg.run_id, video_id))
        return j.model_dump()

    ready = [r["video_id"] for r in ctx.db.query(
        "SELECT video_id FROM videos WHERE run_id=? AND status IN ('processed_local','processed')",
        (ctx.cfg.run_id,))]
    ctx.runner.run("s4_judge", ready, judge_worker, concurrency=int(limits["llm_concurrency"]))

    # replacements for 1053/failed media: next best from cached rank, <=2 rounds
    for _ in range(2):
        failed = ctx.db.query(
            "SELECT v.video_id, v.creator_id, v.role FROM videos v JOIN tasks t"
            " ON t.run_id=v.run_id AND t.entity_id=v.video_id AND t.stage IN ('s4_media','s4_judge')"
            " WHERE v.run_id=? AND t.status='failed' AND v.status NOT IN ('processed','processed_local')",
            (ctx.cfg.run_id,))
        if not failed:
            break
        extra = []
        used = {r["video_id"] for r in ctx.db.query(
            "SELECT video_id FROM videos WHERE run_id=?", (ctx.cfg.run_id,))}
        for fr in failed:
            vids = res_a.get(fr["creator_id"], {}).get("videos", [])
            cand = next((v for v in sorted(vids, key=lambda v: -(v.get("revenue") or 0))
                         if v["video_id"] not in used), None)
            if cand:
                extra.append({"video_id": cand["video_id"], "creator_id": fr["creator_id"],
                              "role": fr["role"] + "_replacement"})
                used.add(cand["video_id"])
        if not extra:
            break
        events.append(f"thay thế {len(extra)} video lỗi 1053/media bằng video kế tiếp trong rank đã cache")
        with ctx.db.transaction() as conn:
            for p in extra:
                conn.execute("INSERT OR IGNORE INTO videos (run_id, video_id, creator_id, role, status)"
                             " VALUES (?,?,?,?,'pending')",
                             (ctx.cfg.run_id, p["video_id"], p["creator_id"], p["role"]))
        ctx.runner.run("s4_media", [p["video_id"] for p in extra], media_worker,
                       concurrency=int(limits["io_concurrency"]))
        ready2 = [r["video_id"] for r in ctx.db.query(
            "SELECT video_id FROM videos WHERE run_id=? AND status='processed_local'",
            (ctx.cfg.run_id,))]
        ctx.runner.run("s4_judge", ready2, judge_worker, concurrency=int(limits["llm_concurrency"]))

    # finalize cards: visual + knowledge
    jrows = ctx.runner.done_results("s4_judge")
    s3j = s3["judgements"]
    # map video→creator từ bảng videos (VideoStats không có creator_id; gồm cả video thay thế)
    v2c = {r["video_id"]: r["creator_id"] for r in ctx.db.query(
        "SELECT video_id, creator_id FROM videos WHERE run_id=?", (ctx.cfg.run_id,))}
    for cid in kept:
        vjs = [j for vid_, j in jrows.items() if v2c.get(vid_) == cid]
        card = cards[cid]
        vis, vparts = visual_score(vjs, 15.0)
        card.visual = vis
        card.visual_measured_max = vparts["measured_max"]
        knowledge = (sum(j.get("knowledge_accuracy", 0.5) for j in vjs) / len(vjs)) if vjs else None
        r_a = res_a.get(cid, {})
        s3jud = s3j.get(cid, {})
        hits = s3jud.get("competitor_names", []) if s3jud.get("competitor_mention") else []
        content, cparts = content_score_text(r_a.get("niche_ratio", 0),
                                             r_a.get("metrics", {}).get("ad_ratio", 0), hits,
                                             llm_fit=s3jud.get("niche_fit"), knowledge=knowledge)
        card.content = content
        card.content_measured_max = cparts["measured_max"]
        for j in vjs:
            if j.get("knowledge_issues"):
                card.flags.append({"flag": "knowledge_issue",
                                   "detail": "; ".join(j["knowledge_issues"])[:250]})
            if j.get("exaggerated_claims"):
                card.flags.append({"flag": "exaggerated_claims",
                                   "detail": "; ".join(j["exaggerated_claims"])[:250]})
            if j.get("ad_disclosure_ok") is False:
                card.flags.append({"flag": "ad_no_disclosure", "detail": "video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý"})

    out = {"cards": {k: v.model_dump() for k, v in cards.items()},
           "video_judgements": jrows, "events": events,
           "videos_planned": len(planned)}
    ctx.put_stage_result("s4", out)
    return out


def load(ctx) -> dict:
    r = ctx.stage_result("s4")
    return r if r else run(ctx)
