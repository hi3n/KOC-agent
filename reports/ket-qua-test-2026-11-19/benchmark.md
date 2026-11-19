# Benchmark — run `demo_sunscreen`

Mọi số từ `usage_ledger` (đo thật). Credit→USD quy đổi tham khảo 0.1.


## Lần chạy LẠNH (cache trống, trả tiền thật)

| Tầng | Provider | Calls | Credit | Token in | Token out | Cache tokens | AI USD | Avg ms |
|---|---|---|---|---|---|---|---|---|
| s0 | kalodata | 1 | 0.1 | 0 | 0 | 0 | 0.0000 | 200 |
| s0 | llm | 1 | 0.0 | 6,453 | 506 | 0 | 0.0180 | 148535 |
| s1 | kalodata | 4 | 0.4 | 0 | 0 | 0 | 0.0000 | 2740 |
| s2a | kalodata | 30 | 3.0 | 0 | 0 | 0 | 0.0000 | 2275 |
| s2b | kalodata | 18 | 1.8 | 0 | 0 | 0 | 0.0000 | 813 |
| s3 | llm | 9 | 0.0 | 67,804 | 19,435 | 0 | 0.3300 | 66698 |
| s4 | asr | 28 | 0.0 | 0 | 0 | 0 | 0.0000 | 100957 |
| s4 | kalodata | 15 | 7.5 | 0 | 0 | 0 | 0.0000 | 239 |
| s4 | llm | 14 | 0.0 | 89,749 | 20,702 | 0 | 0.7730 | 29903 |
| s5 | llm | 7 | 0.0 | 139,902 | 46,826 | 0 | 0.7481 | 100015 |

**Tổng LẠNH**: 12.8 credit · $1.8690 AI · 391,377 token · 4792s tổng thời gian tác vụ (song song nên wall-clock nhỏ hơn).

## Lần chạy ẤM (cache hit, resume/replay)

| Tầng | Provider | Calls | Credit | Token in | Token out | Cache tokens | AI USD | Avg ms |
|---|---|---|---|---|---|---|---|---|
| s1 | kalodata | 4 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |
| s2a | kalodata | 30 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |
| s2b | kalodata | 18 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |
| s4 | llm | 14 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |

**Tổng ẤM**: 0.0 credit · $0.0000 AI · 0 token · 0s tổng thời gian tác vụ (song song nên wall-clock nhỏ hơn).

## Ngoại suy N=500 (đơn giá ĐO được, giả định ghi rõ)

- Đơn giá phân tích 1 video (đo): LLM $0.0552 + video/url 0.5cr = **$0.1052**
- Ngây thơ (500 KOC × 5 video, không phễu): ≈ **$273.04** + Kalodata
- Phễu (500→100→20→5, 75 video, tỷ lệ theo plan): ≈ **$13.99**
- **Giảm ≈ 95%** chi phí phân tích video. Giả định: tỷ lệ sống sót 500→100→20, 3 video/KOC top-20; đo lại khi chạy 500 thật.

## Phục hồi (resume)

- Warm ở trên = toàn bộ pipeline chạy lại với cache giữ nguyên: credit/token/cost thêm phải = 0 cho phần đã xong.
- Kill -9 demo: xem `resume_demo.json` (nếu có) — script chạy, kill giữa chừng, resume, so kết quả + chi phí thêm.
```
{
 "killed_at": {
  "s2a_done": 3,
  "elapsed_s": 2.5
 },
 "stale_running_reset": 3,
 "cold_credits_at_kill": null,
 "cold_credits_after_resume": null,
 "extra_credits_for_done_work": 0,
 "extra_ai_cost_for_done_work": 0,
 "results_csv_identical_to_baseline": true,
 "compare_note": "bỏ cột contact_* (fixtures public đã scrub vì privacy); so từng giá trị còn lại",
 "verdict": "PASS"
}
```

## Kiểm chứng bằng chứng & số liệu (Validator + Numeric Audit)

- **Tỷ lệ lý do pass `validate_reason` (mã `evidence_id` hợp lệ + `videos_watched` khớp DB):** **7/7** (100%)
- **Dry-run Numeric Claim Audit (đối chiếu con số trong `strengths.claim` với dữ liệu gốc):**
  - Khớp trực tiếp trong `evidence_id` được trích tại dòng đó: **54/57** (94.7%)
  - Khớp trong bản ghi evidence/hồ sơ khác của cùng creator: **3/57**
  - Tổng số liệu truy nguyên được về dữ liệu gốc: **57/57** (100.0% · số không khớp: 0)