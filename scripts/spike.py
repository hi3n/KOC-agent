"""API spike: 6 live calls to confirm payloads before locking schemas.

Records fixtures through the real client path, calibrates credit estimates
against credit/balance, downloads one sample video. Run: uv run python scripts/spike.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from koc.config import build_config
from koc.db import Database
from koc.kalodata import KalodataClient, KalodataError
from koc.ledger import Ledger

ROOT = Path(__file__).resolve().parents[1]


def show(label: str, data, sample_chars: int = 700):
    print(f"\n### {label}")
    if isinstance(data, list):
        print(f"list[{len(data)}]")
        if data:
            print("fields:", sorted(data[0].keys()) if isinstance(data[0], dict) else type(data[0]))
            print("sample:", json.dumps(data[0], ensure_ascii=False, default=str)[:sample_chars])
    elif isinstance(data, dict):
        print("fields:", sorted(data.keys()))
        print("sample:", json.dumps(data, ensure_ascii=False, default=str)[:sample_chars])
    else:
        print(repr(data)[:sample_chars])


def main():
    cfg = build_config(ROOT / "config" / "defaults.yaml")
    db = Database(ROOT / "runs" / "spike" / "spike.db")
    ledger = Ledger(db, "spike")
    key = os.environ.get("KALO_API_KEY", "")
    if not key:
        print("KALO_API_KEY missing in .env")
        return
    kd = KalodataClient(db, ledger, cfg.kalodata, key, mode="rw",
                        fixtures_dir=ROOT / "fixtures", date_range=cfg.date_range)
    print("date_range:", cfg.date_range)
    try:
        bal0 = kd.balance()
        print("balance before:", json.dumps(bal0, ensure_ascii=False)[:300])
    except Exception as e:
        bal0 = None
        print("balance failed:", e)

    # 1. categories — find sunscreen leaf.
    # Spike finding: category endpoints accept ONLY named ranges (code 501 on
    # absolute ranges) -> use last30Day + TTL 24h (relative range drifts daily).
    cat_id = None
    try:
        cp = kd.base_params(category_level=3, page_size=100, page_number=1,
                            sort_field={"field": "revenue", "type": "DESC"})
        cp["date_range"] = "last30Day"
        cats = kd.call("category/rank", cp, "spike", ttl=86400)
        show("category/rank level3", cats)
        rows = cats if isinstance(cats, list) else cats.get("list", cats.get("rank_list", []))
        for r in rows if isinstance(rows, list) else []:
            name = str(r.get("category_name", r.get("name", ""))).lower()
            if "chống nắng" in name or "sunscreen" in name or "sun care" in name:
                cat_id = str(r.get("category_id", r.get("id")))
                print("MATCH sunscreen category:", cat_id, r.get("category_name", r.get("name")))
                break
    except KalodataError as e:
        print("category/rank error:", e)

    # 2. creator rank
    creator_id = None
    try:
        params = kd.base_params(page_size=20, page_number=1,
                                sort_field={"field": "revenue", "type": "DESC"})
        if cat_id:
            params["category_id_list"] = cat_id
        else:
            params["keyword"] = "kem chống nắng"
        cr = kd.call("creator/rank", params, "spike")
        show("creator/rank", cr)
        rows = cr if isinstance(cr, list) else cr.get("list", cr.get("rank_list", []))
        if isinstance(rows, list) and rows:
            creator_id = str(rows[0].get("creator_id", rows[0].get("id", "")))
            print("first creator_id:", creator_id)
    except KalodataError as e:
        print("creator/rank error:", e)

    # 3. creator detail
    if creator_id:
        try:
            p = kd.base_params(creator_id=creator_id)
            if cat_id:
                p["category_ids"] = [cat_id]
            cd = kd.call("creator/detail", p, "spike")
            show("creator/detail", cd, 1200)
        except KalodataError as e:
            print("creator/detail error:", e)

    # 4. video rank for creator
    video_id = None
    try:
        p = kd.base_params(page_size=20, page_number=1,
                           sort_field={"field": "revenue", "type": "DESC"})
        if creator_id:
            p["creator_id"] = creator_id
        vr = kd.call("video/rank", p, "spike")
        show("video/rank", vr)
        rows = vr if isinstance(vr, list) else vr.get("list", vr.get("rank_list", []))
        if isinstance(rows, list) and rows:
            video_id = str(rows[0].get("video_id", rows[0].get("id", "")))
            print("first video_id:", video_id)
    except KalodataError as e:
        print("video/rank error:", e)

    # 5. video detail (need_extra probe)
    if video_id:
        try:
            vd = kd.call("video/detail", kd.base_params(video_id=video_id, need_extra=True), "spike")
            show("video/detail need_extra", vd, 900)
        except KalodataError as e:
            print("video/detail error:", e)

    # 6. video url + immediate download
    if video_id:
        try:
            vu = kd.call("video/url", {"video_id": video_id}, "spike")
            show("video/url", vu, 300)
            url = None
            if isinstance(vu, dict):
                for k in ("url", "video_url", "download_url", "play_url"):
                    if vu.get(k):
                        url = vu[k]
                        break
            if url:
                import httpx
                out = ROOT / "runs" / "spike" / "sample.mp4"
                with httpx.stream("GET", url, timeout=120, follow_redirects=True) as r:
                    r.raise_for_status()
                    with open(out, "wb") as f:
                        for chunk in r.iter_bytes(1 << 16):
                            f.write(chunk)
                print("downloaded:", out, out.stat().st_size, "bytes")
        except (KalodataError, Exception) as e:
            print("video/url error:", e)

    try:
        bal1 = kd.balance()
        print("\nbalance after:", json.dumps(bal1, ensure_ascii=False)[:300])
        if bal0 and bal1:
            r0 = bal0.get("data", {}).get("totalRemain")
            r1 = bal1.get("data", {}).get("totalRemain")
            if r0 is not None and r1 is not None:
                print(f"CREDIT DELTA: {r0} -> {r1} = {float(r0) - float(r1):.2f} credits spent")
    except Exception as e:
        print("balance after failed:", e)
    print("\nledger rollup:")
    for r in ledger.rollup():
        print(" ", r)
    kd.close()
    db.close()


if __name__ == "__main__":
    main()
