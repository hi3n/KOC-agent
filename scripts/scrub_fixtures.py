"""Scrub thông tin liên hệ creator khỏi fixtures trước khi commit repo public.

creator/detail responses chứa email/zalo/facebook... — dữ liệu cá nhân, không
được đưa lên GitHub. Cache key = hash(endpoint + PARAMS), không gồm response →
scrub không phá replay. Kết quả: replay offline vẫn chạy đủ, results.csv của
replay sẽ trống cột contact (bản chạy live giữ contact trong DB local).
Usage: uv run python scripts/scrub_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = Path(__file__).resolve().parents[1]
CONTACT_PREFIX = "creator_contact_"


def scrub_obj(o):
    n = 0
    if isinstance(o, dict):
        for k, v in list(o.items()):
            if k.startswith(CONTACT_PREFIX) and v:
                o[k] = ""
                n += 1
            else:
                n += scrub_obj(v)
    elif isinstance(o, list):
        for v in o:
            n += scrub_obj(v)
    return n


def main():
    total = 0
    for p in (ROOT / "fixtures").glob("*.json"):
        obj = json.loads(p.read_text(encoding="utf-8"))
        n = scrub_obj(obj)
        if n:
            p.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
            total += n
            print(f"scrubbed {n} contact fields: {p.name}")
    print(f"total: {total} fields")


if __name__ == "__main__":
    main()
