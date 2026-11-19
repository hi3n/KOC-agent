"""Pure-function tests cho dashboard generator (số format VN, evidence text, parse giá)."""
import re

from koc.dashboard import _ev_text, _vn


def test_vn_number_format():
    assert _vn(1234567.89, 2) == "1.234.567,89"
    assert _vn(30000000) == "30.000.000"
    assert _vn(0.7, 2) == "0,70"
    assert _vn(None) == "None" or _vn(None) == ""  # không crash


def test_scale_label():
    lab = lambda s: _vn(s, 2).rstrip("0").rstrip(",") + "×"
    assert lab(1.0) == "1×"
    assert lab(0.7) == "0,7×"
    assert lab(1.03) == "1,03×"
    assert lab(1.5) == "1,5×"


def test_ev_text_kinds():
    q = _ev_text("transcript_quote", {"quote": "một lớp kem chống nắng", "start_s": 70.5})
    assert "70,5s" in q and "một lớp kem chống nắng" in q
    m = _ev_text("metric", {"median_views": 6996, "median_er": 0.0077, "n_videos": 65})
    assert "6.996" in m and "65 video" in m
    assert _ev_text("unknown_kind", {}) == ""


def test_cheapest_parse_english_format():
    reason = "không bộ 5 nào <= 30,000,000 VNĐ; rẻ nhất có thể: 33,350,000 VNĐ. Giảm slot"
    m = re.search(r"rẻ nhất có thể:\s*([\d.,]+)", reason)
    assert m
    cheapest = float(re.sub(r"[.,]", "", m.group(1))) / 1e6
    assert cheapest == 33.35
