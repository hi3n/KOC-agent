"""Code-side scoring: performance metrics, red flags, coverage-aware scorecards.

Design reasons (ARCHITECTURE.md D2/D9):
- All arithmetic is deterministic code, never LLM: free, reproducible, and every
  number traces back to raw API rows (evidence).
- ER is self-computed ((like+comment+share)/view) — never mixed with Kalodata's
  LOW/MEDIUM/HIGH buckets, which use a different definition.
- Performance sub-scores are pool-relative percentiles, not absolute thresholds:
  thresholds don't transfer across niches; percentiles are transparent and need
  no magic constants. Red flags stay absolute (from tieu-chi-chon-koc.md).
- Scores carry coverage: audience (25) + collaboration (10) are NOT auto-scored;
  measurable max = 65. Display "measured X/65", never a fake /100.
"""
from __future__ import annotations

import statistics

from pydantic import BaseModel, Field


class VideoStats(BaseModel):
    video_id: str
    title: str = ""
    views: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    revenue: float = 0.0
    published: str = ""
    is_ad: bool = False
    is_ai: bool = False


def _pick(row: dict, keys: list[str], default=None):
    for k in keys:
        if k in row and row[k] is not None:
            return row[k]
    return default


def _to_int(v) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return 0


def normalize_video(row: dict) -> VideoStats:
    """Map Kalodata video row -> internal model. Field names confirmed by spike;
    candidate lists keep this tolerant to naming variants."""
    pub = _pick(row, ["publish_date", "published_at", "publish_time", "create_time", "created_at"], "")
    return VideoStats(
        video_id=str(_pick(row, ["video_id", "id", "item_id"], "")),
        title=str(_pick(row, ["title", "video_title", "desc"], "") or ""),
        views=_to_int(_pick(row, ["views", "play_count", "view_count", "content_views", "plays"], 0)),
        likes=_to_int(_pick(row, ["likes", "like_count", "digg_count"], 0)),
        comments=_to_int(_pick(row, ["comments", "comment_count"], 0)),
        shares=_to_int(_pick(row, ["shares", "share_count", "forward_count"], 0)),
        revenue=float(_pick(row, ["revenue", "sales_revenue", "gmv"], 0) or 0),
        published=str(pub)[:10] if pub else "",
        is_ad=bool(_to_int(_pick(row, ["ad", "is_ad", "is_ads", "ad_flag", "is_promotion"], 0))),
        is_ai=bool(_to_int(_pick(row, ["ai_video", "is_ai_video", "is_ai"], 0))),
    )


def video_er(v: VideoStats) -> float:
    return (v.likes + v.comments + v.shares) / v.views if v.views > 0 else 0.0


def performance_metrics(videos: list[VideoStats], followers: int, period_days: int = 30) -> dict:
    if not videos:
        return {"n_videos": 0}
    views = [v.views for v in videos]
    ers = [video_er(v) for v in videos if v.views > 0]
    med_views = statistics.median(views)
    mean_views = statistics.mean(views)
    latest = max((v.published for v in videos if v.published), default="")
    return {
        "n_videos": len(videos),
        "median_views": med_views,
        "mean_views": round(mean_views, 1),
        "median_er": round(statistics.median(ers), 5) if ers else 0.0,
        "mean_er": round(statistics.mean(ers), 5) if ers else 0.0,
        "view_follower_ratio": round(med_views / followers, 4) if followers > 0 else 0.0,
        "stability": round(med_views / mean_views, 3) if mean_views > 0 else 0.0,
        "posts_per_week": round(len(videos) / (period_days / 7), 2),
        "ad_ratio": round(sum(v.is_ad for v in videos) / len(videos), 3),
        "ai_ratio": round(sum(v.is_ai for v in videos) / len(videos), 3),
        "total_revenue": round(sum(v.revenue for v in videos), 2),
        "latest_publish": latest,
    }


def red_flags(m: dict, cfg_flags: dict, competitor_hits: list[str]) -> list[dict]:
    """Absolute thresholds from tieu-chi-chon-koc.md. Each flag carries its numbers."""
    flags = []
    if m.get("n_videos", 0) == 0:
        flags.append({"flag": "no_video_data", "detail": "không có video trong kỳ"})
        return flags
    if m["median_er"] < cfg_flags.get("min_er", 0.005):
        flags.append({"flag": "low_er", "detail": f"median ER {m['median_er']:.4f} < {cfg_flags['min_er']}"})
    if m["view_follower_ratio"] < cfg_flags.get("min_view_follower_ratio", 0.02):
        flags.append({"flag": "cold_channel", "detail": f"view/follower {m['view_follower_ratio']:.3f} thấp — kênh nguội hoặc follower ảo"})
    if m["ad_ratio"] > cfg_flags.get("max_ad_ratio", 0.8):
        flags.append({"flag": "ad_saturated", "detail": f"tỷ lệ video quảng cáo {m['ad_ratio']:.2f} — uy tín thấp"})
    if competitor_hits:
        flags.append({"flag": "competitor_recent", "detail": "nhắc đối thủ: " + ", ".join(competitor_hits[:5])})
    if m.get("new_follower_ratio", 0) > 0.2:
        flags.append({"flag": "follower_spike", "detail": f"follower mới/kỳ = {m['new_follower_ratio']:.0%} tổng follower — tăng bất thường"})
    # spike thật 19/11: có creator ER trung vị 8.22 (tương tác > view — view Kalodata
    # là ước tính). Không chấm thầm lặng trên dữ liệu dị: cờ cho người duyệt + cap khi chấm.
    if m.get("median_er", 0) > 1.0:
        flags.append({"flag": "er_anomaly", "detail": f"ER trung vị {m['median_er']:.2f} > 100% — dữ liệu view bất thường (ước tính Kalodata); đã cap về 1.0 khi chấm, cần kiểm tra thủ công"})
    elif m.get("median_er", 0) > 0.3:
        flags.append({"flag": "er_unusually_high", "detail": f"ER trung vị {m['median_er']:.2f} cao bất thường — có thể kênh nhỏ/viral hoặc view ước tính thấp; kiểm tra mẫu video"})
    return flags


def scoring_er(m: dict) -> float:
    """ER dùng cho chấm điểm: cap 1.0 (dữ liệu dị không được khuếch đại percentile).
    Số thô giữ nguyên trong metrics/evidence để truy vết."""
    return min(float(m.get("median_er", 0)), 1.0)


def percentile_rank(value: float, pool: list[float]) -> float:
    if not pool:
        return 0.5
    below = sum(1 for x in pool if x < value)
    equal = sum(1 for x in pool if x == value)
    return (below + 0.5 * equal) / len(pool)


def performance_score(m: dict, pcts: dict, weight: float = 25.0) -> tuple[float, dict]:
    """pcts: percentile (0..1) of this creator vs pool for each sub-metric."""
    if m.get("n_videos", 0) == 0:
        return 0.0, {"reason": "no data"}
    parts = {
        "reach": pcts.get("median_views", 0.5),          # view trung vị > follower
        "engagement": pcts.get("median_er", 0.5),
        "audience_activity": pcts.get("view_follower_ratio", 0.5),
        "consistency": pcts.get("stability", 0.5),        # median/mean: viral skew thấp
        "frequency": pcts.get("posts_per_week", 0.5),
    }
    score = weight * sum(parts.values()) / len(parts)
    return round(score, 2), parts


def content_score_text(niche_ratio: float, ad_ratio: float, competitor_hits: list[str],
                       llm_fit: float | None = None, knowledge: float | None = None,
                       weight: float = 25.0) -> tuple[float, dict]:
    """Content 25đ, đo dần theo tầng:
    code (S2): niche_keyword 8 + ad_trust 4 + competitor 4 = 16
    LLM text (S3): semantic_fit 5
    LLM video (S4): knowledge_accuracy 4
    Phần chưa đo KHÔNG bị tính 0 oan — coverage giảm, điểm chuẩn hóa nội bộ
    chỉ trên phần đã đo (kèm phạt coverage khi xếp hạng)."""
    parts = {}
    measured = 0.0
    total = 25.0
    parts["niche_keyword"] = round(8.0 * min(1.0, niche_ratio * 2), 2)  # >=50% video đúng ngách = full
    measured += 8.0
    parts["ad_trust"] = round(4.0 * max(0.0, 1.0 - max(0.0, ad_ratio - 0.4) / 0.6), 2)
    measured += 4.0
    parts["competitor"] = 0.0 if competitor_hits else 4.0
    measured += 4.0
    if llm_fit is not None:
        parts["semantic_fit"] = round(5.0 * llm_fit, 2)
        measured += 5.0
    if knowledge is not None:
        parts["knowledge"] = round(4.0 * knowledge, 2)
        measured += 4.0
    # điểm THÔ trên phần đã đo (không scale gian lận về 25); coverage đi kèm
    # để chuẩn hóa nội bộ + phạt khi xếp hạng (ScoreCard.internal_rank_score)
    score = sum(parts.values())
    return round(score, 2), {"parts": parts, "measured_max": measured, "max": total}


def visual_score(video_judgements: list[dict], weight: float = 15.0) -> tuple[float, dict]:
    """video_judgements: S4 outputs {visual_quality: 0..1, demo_quality: 0..1,
    hook_strength: 0..1, audio_clarity: 0..1, knowledge_accuracy: 0..1}."""
    if not video_judgements:
        return 0.0, {"measured_max": 0.0, "max": weight}
    keys = ["visual_quality", "demo_quality", "hook_strength", "audio_clarity"]
    vals = {k: statistics.mean(float(j.get(k, 0.5)) for j in video_judgements) for k in keys}
    score = weight * sum(vals.values()) / len(keys)
    return round(score, 2), {"parts": vals, "measured_max": weight, "max": weight,
                             "n_videos_judged": len(video_judgements)}


def niche_ratio(videos: list[VideoStats], keywords: list[str]) -> float:
    if not videos or not keywords:
        return 0.0
    kws = [k.lower() for k in keywords]
    hit = sum(1 for v in videos if any(k in v.title.lower() for k in kws))
    return hit / len(videos)


def competitor_hits(videos: list[VideoStats], top_products: list[str], competitors: list[str]) -> list[str]:
    if not competitors:
        return []
    texts = [v.title.lower() for v in videos] + [str(p).lower() for p in top_products]
    return sorted({c for c in competitors if any(c.lower() in t for t in texts)})


class ScoreCard(BaseModel):
    """Điểm theo phần đã đo / chưa đo — không gộp thành /100 giả."""
    creator_id: str
    performance: float = 0.0
    content: float = 0.0
    visual: float = 0.0
    content_measured_max: float = 0.0
    visual_measured_max: float = 0.0
    audience: float | None = None        # không tự chấm
    collaboration: float | None = None   # không tự chấm
    flags: list[dict] = Field(default_factory=list)
    niche_cluster: str = "other"
    excluded: bool = False
    exclude_reason: str = ""

    @property
    def measured(self) -> float:
        return round(self.performance + self.content + self.visual, 2)

    @property
    def measured_max(self) -> float:
        return round(25.0 + self.content_measured_max + self.visual_measured_max, 2)

    def internal_rank_score(self, coverage_penalty: float = 0.15) -> float:
        """Chuẩn hóa nội bộ để xếp hạng/chọn tổ hợp; phạt coverage thấp.
        KHÔNG hiển thị ra ngoài như điểm tuyệt đối."""
        if self.measured_max <= 0:
            return 0.0
        norm = self.measured / self.measured_max
        coverage = self.measured_max / 65.0
        return round(norm * (1 - coverage_penalty * (1 - coverage)), 4)
