from koc.scoring import (ScoreCard, content_score_text, normalize_video,
                         performance_metrics, red_flags, scoring_er, video_er, visual_score)


def test_er_anomaly_flagged_and_capped():
    m = {"n_videos": 5, "median_er": 8.22, "view_follower_ratio": 0.5, "ad_ratio": 0.1}
    flags = {f["flag"] for f in red_flags(m, {"min_er": 0.005}, [])}
    assert "er_anomaly" in flags
    assert scoring_er(m) == 1.0  # cap cho chấm điểm, số thô giữ trong evidence
    m2 = dict(m, median_er=0.49)
    assert "er_unusually_high" in {f["flag"] for f in red_flags(m2, {"min_er": 0.005}, [])}


def test_normalize_spike_shape():
    row = {"video_id": "1", "video_title": "review kem chống nắng", "views": 1000,
           "digg_count": 50, "comment_count": 10, "share_count": 5,
           "publish_date": "2026-10-23 19:13:38", "ad": 1, "ai_video": 0, "revenue": 12.5}
    v = normalize_video(row)
    assert v.likes == 50 and v.is_ad is True and v.is_ai is False
    assert v.published == "2026-10-23"
    assert abs(video_er(v) - 0.065) < 1e-9


def test_metrics_median_vs_mean():
    vids = [normalize_video({"video_id": str(i), "views": v, "digg_count": 10,
                             "comment_count": 2, "share_count": 1})
            for i, v in enumerate([100, 100, 100, 10000])]
    m = performance_metrics(vids, followers=1000)
    assert m["median_views"] == 100 and m["mean_views"] == 2575.0
    assert m["stability"] < 0.1  # viral skew detected
    assert m["view_follower_ratio"] == 0.1


def test_red_flags():
    m = {"n_videos": 5, "median_er": 0.001, "view_follower_ratio": 0.5,
         "ad_ratio": 0.9, "new_follower_ratio": 0.5}
    flags = {f["flag"] for f in red_flags(m, {"min_er": 0.005, "max_ad_ratio": 0.8}, ["Anessa"])}
    assert {"low_er", "ad_saturated", "competitor_recent", "follower_spike"} <= flags


def test_content_coverage_grows():
    s0, p0 = content_score_text(0.6, 0.2, [])
    assert p0["measured_max"] == 16.0 and s0 == 16.0  # niche full 8 + trust 4 + competitor 4
    s1, p1 = content_score_text(0.6, 0.2, [], llm_fit=0.8)
    assert p1["measured_max"] == 21.0 and s1 == 20.0
    s2, p2 = content_score_text(0.6, 0.2, [], llm_fit=0.8, knowledge=1.0)
    assert p2["measured_max"] == 25.0 and s2 == 24.0
    s3, _ = content_score_text(0.6, 0.2, ["Anessa"], llm_fit=0.8, knowledge=1.0)
    assert s3 == 20.0  # competitor conflict zeroes 4đ


def test_scorecard_no_fake_100():
    c = ScoreCard(creator_id="x", performance=20, content=16, content_measured_max=16)
    assert c.measured == 36 and c.measured_max == 41
    assert c.internal_rank_score() < c.measured / c.measured_max  # coverage penalty applies
    v, parts = visual_score([{"visual_quality": 0.8, "demo_quality": 0.6,
                              "hook_strength": 0.7, "audio_clarity": 0.9}])
    assert parts["measured_max"] == 15.0 and 0 < v < 15
