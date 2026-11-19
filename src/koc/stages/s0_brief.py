"""S0 — AI phân tích brief, grounded trên cây danh mục thật (D3).

1 call LLM (role=brief), cache theo hash(brief+categories+prompt+model).
Code validates: category IDs phải tồn tại, budget clamp, objective enum.
Fallback không LLM: keyword match trên tên danh mục (offline không key vẫn chạy
nếu judgement đã cache; chạy mới hoàn toàn không key → dừng rõ ràng).
"""
from __future__ import annotations

from ..config import BriefAnalysis
from ..evidence import record
from ..llm import LLMUnavailable
from ..prompts import S0_SYSTEM


def fetch_categories(ctx) -> list[dict]:
    params = ctx.kd.base_params(category_level=3, page_size=100, page_number=1,
                                sort_field={"field": "revenue", "type": "DESC"})
    params["date_range"] = "last30Day"   # category endpoint chỉ nhận named range (spike: code 501)
    data = ctx.kd.call("category/rank", params, "s0", ttl=86400)
    rows = data if isinstance(data, list) else data.get("list", [])
    return [{"category_id": str(r.get("category_id")), "category_name": r.get("category_name", "")}
            for r in rows]


def _keyword_fallback(cats: list[dict]) -> list[str]:
    # specific-first: chỉ nới sang kw rộng khi không có match đặc thù —
    # tránh lệch category_ids so với run đã cache (smoke 19/11: match lẫn "chăm sóc da")
    specific = ["chống nắng", "sunscreen", "sun care"]
    broad = ["skincare", "chăm sóc da"]
    hits = [c["category_id"] for c in cats
            if any(k in c["category_name"].lower() for k in specific)]
    if not hits:
        hits = [c["category_id"] for c in cats
                if any(k in c["category_name"].lower() for k in broad)]
    return hits[:3]


def run(ctx) -> BriefAnalysis:
    if ctx.cfg.brief_analysis is not None:
        return ctx.cfg.brief_analysis  # resume / offline snapshot
    if not ctx.cfg.brief_text.strip():
        raise RuntimeError("S0 cần brief text (briefs/sunscreen.txt) hoặc config snapshot")
    try:
        cats = fetch_categories(ctx)
    except Exception as e:
        cats = []  # kể cả offline thiếu fixture: vẫn degraded được, S1 dùng keyword
        record(ctx.db, ctx.cfg.run_id, "s0", "degraded", "category_fetch_failed", {"error": str(e)[:300]})
    cat_list = "\n".join(f"{c['category_id']}|{c['category_name']}" for c in cats)
    user = (f"<brief>\n{ctx.cfg.brief_text}\n</brief>\n\n"
            f"<kalodata_categories level=3 top100 theo doanh thu>\n{cat_list}\n</kalodata_categories>\n\n"
            "Phân tích brief và trả về BriefAnalysis JSON. category_ids chỉ lấy từ danh sách trên.")
    llm = ctx.llm("brief", "s0")
    try:
        analysis: BriefAnalysis = llm.judge(S0_SYSTEM, user, BriefAnalysis, entity_id="brief")
    except LLMUnavailable as e:
        # DEGRADE, DON'T STOP: mọi provider fail → YAML defaults + keyword match,
        # đánh dấu trung thực để người duyệt cấu hình trước khi tin kết quả
        cd = ctx.cfg.raw.get("campaign_defaults", {})
        fb = _keyword_fallback(cats)
        analysis = BriefAnalysis(
            product=cd.get("product", "kem chống nắng"),
            category_ids=fb,
            category_names=[c["category_name"] for c in cats if c["category_id"] in fb],
            niche_keywords=cd.get("niche_keywords", ["kem chống nắng", "chống nắng", "sunscreen", "spf"]),
            audience_gender=cd.get("audience", {}).get("gender", "female"),
            audience_age_range=cd.get("audience", {}).get("age_range", "18-30"),
            audience_region=cd.get("audience", {}).get("region", "VN"),
            objective=cd.get("objective", "conversion"),
            budget_vnd=int(ctx.cfg.raw["budget"]["total_vnd"]),
            rationale=(f"DEGRADED — LLM không gọi được ({str(e)[:200]}). Dùng campaign_defaults YAML "
                       "+ keyword match trên cây danh mục thật. Cần người duyệt cấu hình này "
                       "trước khi tin kết quả; chạy lại S0 khi có provider hoạt động."))
        record(ctx.db, ctx.cfg.run_id, "s0", "degraded", "llm_unavailable",
               {"error": str(e)[:500], "fallback": "yaml_defaults+keyword_match"})

    valid_ids = {c["category_id"] for c in cats}
    bad = [i for i in analysis.category_ids if i not in valid_ids]
    if bad or not analysis.category_ids:
        fb = _keyword_fallback(cats)
        analysis.category_ids = [i for i in analysis.category_ids if i in valid_ids] or fb
        analysis.rationale += f" [code sửa: ID không hợp lệ {bad} → fallback keyword {fb}]"
    if analysis.objective not in ("conversion", "awareness"):
        analysis.objective = "conversion"
    analysis.budget_vnd = max(1_000_000, min(1_000_000_000, int(analysis.budget_vnd)))
    if not analysis.niche_keywords:
        analysis.niche_keywords = ["kem chống nắng", "chống nắng", "sunscreen", "spf"]

    record(ctx.db, ctx.cfg.run_id, "s0", "brief_analysis", "briefs/sunscreen.txt",
           analysis.model_dump())
    from ..pipeline import save_brief_analysis
    save_brief_analysis(ctx, analysis)
    return analysis
