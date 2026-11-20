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
| s4 | llm | 34 | 0.0 | 375,951 | 14,860 | 0 | 0.3377 | 29630 |
| s5 | llm | 1 | 0.0 | 22,470 | 9,353 | 0 | 0.1385 | 194620 |

**Tổng LẠNH**: 12.8 credit · $0.8241 AI · 516,832 token · 4875s tổng thời gian tác vụ (song song nên wall-clock nhỏ hơn).

## Lần chạy ẤM (cache hit, resume/replay)

| Tầng | Provider | Calls | Credit | Token in | Token out | Cache tokens | AI USD | Avg ms |
|---|---|---|---|---|---|---|---|---|
| s1 | kalodata | 4 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |
| s2a | kalodata | 30 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |
| s2b | kalodata | 18 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |
| s5 | llm | 1 | 0.0 | 0 | 0 | 0 | 0.0000 | 0 |

**Tổng ẤM**: 0.0 credit · $0.0000 AI · 0 token · 0s tổng thời gian tác vụ (song song nên wall-clock nhỏ hơn).

## Ngoại suy N=500 (đơn giá ĐO được, giả định ghi rõ)

- Đơn giá phân tích 1 video (đo): LLM $0.0106 + video/url 0.5cr = **$0.0606**
- Ngây thơ (500 KOC × 5 video, không phễu): ≈ **$161.38** + Kalodata
- Phễu (500→100→20→5, 75 video, tỷ lệ theo plan): ≈ **$10.64** (khoảng sai số theo tỷ lệ sống sót 60–100 video: **$9.73 – $12.16**)
- **Giảm ≈ 93%** (khoảng **92%–94%**) chi phí phân tích video. Giả định: tỷ lệ sống sót 500→100→20..25, 3 video/KOC; đo lại khi chạy 500 thật.

## Phục hồi (resume)

- Warm ở trên = toàn bộ pipeline chạy lại với cache giữ nguyên: credit/token/cost thêm phải = 0 cho phần đã xong.
- Kill -9 demo: xem `resume_demo.json` (nếu có) — script chạy, kill giữa chừng, resume, so kết quả + chi phí thêm.
```
{
 "killed_at": {
  "s2a_done": 5,
  "elapsed_s": 2.5
 },
 "stale_running_reset": 4,
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
  - Khớp trực tiếp trong `evidence_id` được trích tại dòng đó: **35/38** (92.1%)
  - Khớp trong bản ghi evidence/hồ sơ khác của cùng creator: **3/38**
  - Tổng số liệu truy nguyên được về dữ liệu gốc: **38/38** (100.0% · số không khớp: 0)

## Nhật ký Governor & Quyết định Agent (decisions)

| Stage | Actor | Action | Target | Kết quả | Lý do |
|---|---|---|---|---|---|
| s2 | planner | `proceed` | kept=12 | ✓ Cho phép | Đủ 12 ứng viên (>= 5), tiếp tục S2b/S3 |
| s4 | planner | `inspect_extra_video` | 7230438795933451269:7698302706674404629 | ✗ Governor chặn | BLOCKED: credit_budget 13.0cr exceeded (used 12.8cr + est 0.5cr) |
| s4 | planner | `inspect_extra_video` | 7440289356625576976:7661445881022942484 | ✗ Governor chặn | BLOCKED: credit_budget 13.0cr exceeded (used 12.8cr + est 0.5cr) |
| s5 | planner | `select_portfolio` | PA1 | ✓ Cho phép | Chọn PA1 tối ưu toàn cục trong ngân sách (30,000,000 VNĐ) |