"""Evidence store + reason validator.

Chain: reason -> evidence_id -> source_ref -> api_cache key / file hash+frame /
transcript span. A reason without valid evidence is rejected, not published.
"""
from __future__ import annotations

import json
import re

from .config import canonical_hash
from .db import Database


def record(db: Database, run_id: str, stage: str, kind: str, source_ref: str,
           payload: dict, creator_id: str | None = None,
           video_id: str | None = None) -> str:
    # content-addressed, run_id-independent: cùng bằng chứng → cùng ID ở mọi run
    # → offline replay run mới vẫn hit judgement cache của S5 (lý do trích evidence)
    eid = "ev_" + canonical_hash([creator_id, video_id, kind, source_ref, payload])[:12]
    db.execute(
        "INSERT OR IGNORE INTO evidence (evidence_id, run_id, creator_id, video_id,"
        " stage, kind, source_ref, payload_json) VALUES (?,?,?,?,?,?,?,?)",
        (eid, run_id, creator_id, video_id, stage, kind, source_ref,
         json.dumps(payload, ensure_ascii=False, default=str)))
    return eid


def for_creator(db: Database, run_id: str, creator_id: str) -> list[dict]:
    """Evidence HIỆN HÀNH của creator: dedupe theo (kind, source_ref) giữ bản ghi
    mới nhất (rowid max). Re-run sau khi upstream judgement đổi phiên bản sẽ ghi
    evidence mới cùng source_ref — bản cũ phải bị loại, nếu không prompt S5 phình
    bản stale và hash lệch giữa run live vs replay (bug 19/11: 20 vs 14 rows → cache miss).
    ORDER BY evidence_id: thứ tự ổn định giữa các run."""
    rows = db.query(
        "SELECT * FROM evidence WHERE run_id=? AND creator_id=? AND rowid IN"
        " (SELECT MAX(rowid) FROM evidence WHERE run_id=? AND creator_id=?"
        "  GROUP BY kind, source_ref) ORDER BY evidence_id",
        (run_id, creator_id, run_id, creator_id))
    for r in rows:
        r["payload"] = json.loads(r["payload_json"])
    return rows


def validate_reason(db: Database, run_id: str, reason: dict) -> list[str]:
    """reason: {creator_id, strengths:[{claim, evidence_ids:[...]}], videos_watched:{seen,total}, ...}"""
    issues: list[str] = []
    cid = reason.get("creator_id", "")
    valid_ids = {r["evidence_id"] for r in for_creator(db, run_id, cid)}
    for i, s in enumerate(reason.get("strengths", [])):
        eids = s.get("evidence_ids", [])
        if not eids:
            issues.append(f"strength[{i}] không trích evidence nào")
        for eid in eids:
            if eid not in valid_ids:
                issues.append(f"strength[{i}] trích evidence không tồn tại/không thuộc creator: {eid}")
    vw = reason.get("videos_watched") or {}
    row = db.one("SELECT COUNT(*) n FROM videos WHERE run_id=? AND creator_id=? AND status='processed'",
                 (run_id, cid))
    seen = int(vw.get("seen", -1))
    if row and seen != row["n"]:
        issues.append(f"videos_watched.seen={seen} khác số video đã xử lý thật={row['n']}")
    return issues


def _extract_nums(text: str) -> set[float]:
    out: set[float] = set()
    for m in re.findall(r"\d+(?:[.,]\d+)?", str(text)):
        try:
            out.add(float(m.replace(",", ".")))
        except ValueError:
            pass
    return out


def _num_in_pool(val: float, pool: set[float]) -> bool:
    return any(abs(val - y) <= max(1e-6, abs(y) * 1e-4) for y in pool)


def audit_numeric_claims(db: Database, run_id: str, reasons: list[dict],
                         details: dict | None = None) -> dict:
    """Dry-run audit (chỉ đo, KHÔNG kích hoạt retry S5): đối chiếu mọi con số trong
    strengths.claim với payload của evidence_ids được trích (và kho evidence/hồ sơ
    của cùng creator). Trả về số đo thật cho benchmark."""
    total, in_cited, in_creator = 0, 0, 0
    unmatched: list[dict] = []
    details = details or {}
    for item in reasons:
        cid = item.get("creator_id", "")
        evs = for_creator(db, run_id, cid)
        ev_map = {e["evidence_id"]: e for e in evs}
        creator_nums = _extract_nums(json.dumps([e["payload"] for e in evs], ensure_ascii=False))
        if cid in details:
            creator_nums |= _extract_nums(json.dumps(details[cid], ensure_ascii=False))
        for i, st in enumerate(item.get("strengths", [])):
            cited_blobs = [ev_map[eid]["payload"] for eid in st.get("evidence_ids", []) if eid in ev_map]
            cited_nums = _extract_nums(json.dumps(cited_blobs, ensure_ascii=False))
            for x in sorted(_extract_nums(st.get("claim", ""))):
                total += 1
                if _num_in_pool(x, cited_nums):
                    in_cited += 1
                elif _num_in_pool(x, creator_nums):
                    in_creator += 1
                else:
                    unmatched.append({"creator_id": cid, "strength_idx": i,
                                      "number": x, "claim": st.get("claim", "")[:120]})
    verified = in_cited + in_creator
    return {
        "total_numbers": total,
        "in_cited_evidence": in_cited,
        "in_creator_other_evidence": in_creator,
        "verified_total": verified,
        "unmatched": unmatched,
        "cited_match_rate": round(in_cited / total, 4) if total else 1.0,
        "verified_rate": round(verified / total, 4) if total else 1.0,
    }
