# Kết quả test — AI KOC Discovery

*Xuất 2026-11-19 08:14 UTC từ run `demo_sunscreen` · mọi số truy được về `usage_ledger`/`tasks`/`evidence` trong SQLite · báo cáo 5 KOC chi tiết: `report.md`, `results.csv` · benchmark: `benchmark.md`, `resume_demo.json` · máy đọc: `measurements.json` · bảng S2: `kept.csv`, `excluded.csv`*

**Trạng thái:** ✅ FULL PIPELINE hoàn tất (S0→S5). Unit tests: **26 passed in 2.80s**.


---

## 1. Chất lượng — đề xuất dựa trên bằng chứng

**Đã chạy thật (S0→S5, dữ liệu Kalodata VN, danh mục 601602 "Kem chống nắng cho da mặt"):**

- Pool **30** ứng viên độc lập (`creator_type=INDEPENDENT` — spike phát hiện top revenue là brand store, đã lọc).
- Giữ **12** vào S2b; loại **18** — MỖI người loại có lý do kèm số (`excluded.csv`):
  - 10 red flag ER < 0,5% (ngưỡng bộ tiêu chí; đo từ video thật, không dùng thang ER Kalodata)
  - 3 vượt trần followers giả định 1M (ngoài tầm ngân sách 30tr — giả định ghi rõ)
  - 0 lỗi khác; 5 dưới ngưỡng cắt điểm
- **273 bản ghi evidence** đã lưu (metric/niche_signal/transcript_quote/frame_obs từng creator, truy ngược về khóa api_cache gốc hoặc file video + timestamp).
- Điểm hiển thị **đã đo/chưa đo**: hiệu suất /25 + nội dung /25 + hình ảnh /15 = tối đa **65đ đo được**; khán giả 25đ + hợp tác 10đ KHÔNG tự chấm (không có dữ liệu) → checklist xác minh, không đoán.
- Chuỗi bằng chứng S4→S5: video → frames + transcript timestamp → LLM chấm rubric → `transcript_quote`/`frame_obs` evidence → lý do S5 trích `evidence_id`, validator kiểm tra đối chiếu nguồn.
- Recall audit: mẫu ~10% bị loại ở S2a chấm lại S3 để đo mức bỏ sót của phễu.

**Bộ 5 KOC chính thức + 2 dự phòng được chọn ở S5** (chi tiết đầy đủ bằng chứng & trích dẫn video xem tại `report.md` và `results.csv`):

| Vai trò | KOC | Handle | Followers | Tier | Điểm đã đo | Giá giả định (VNĐ) |
|---|---|---|---|---|---|---|
| Chính thức | Công chúa cam thường | @vanhmakeupcute | 210,500 | anchor | **35.28/65.0** | 7,000,000 |
| Chính thức | Phương Sena | @phuongsena | 261,900 | anchor | **39.43/65.0** | 7,000,000 |
| Chính thức | Chang Chăm Chỉ | @changaffiliate | 85,500 | mid | **33.52/65.0** | 6,000,000 |
| Chính thức | Cẩm Linh | @calinle | 49,700 | micro | **32.93/65.0** | 5,000,000 |
| Chính thức | Khoa Alpha 💪 🇻🇳 | @khoaalpha99 | 49,900 | micro | **31.4/65.0** | 5,000,000 |
| [DỰ PHÒNG] | Kiều Oanh Mê Làm Đẹp | @kieu_oanh_cosmetic | 119,000 | mid | **33.52/65.0** | 6,000,000 |
| [DỰ PHÒNG] | Mỏ hỗn là tao | @mykimmohon | 350,900 | anchor | **32.1/65.0** | 7,000,000 |

**Top ứng viên qua vòng S2** (điểm code trước khi vào LLM S3/S4 — chi tiết `kept.csv`):

| KOC | Followers | Hiệu suất /25 | Nội dung (đo/16) | ER trung vị | View/follower | Cờ |
|---|---|---|---|---|---|---|
| Phương Sena | 261,900 | 11.91 | 16.0/16 | 0.0077 | 0.027 | — |
| Cẩm Linh | 49,700 | 13.38 | 10.46/16 | 0.0354 | 0.117 | — |
| Khoa Alpha 💪 🇻🇳 | 49,900 | 14.56 | 9.08/16 | 0.4902 | 0.080 | er_unusually_high |
| Mỏ hỗn là tao | 350,900 | 18.38 | 4.6/16 | 0.0167 | 0.765 | ad_saturated |
| Chang Chăm Chỉ | 85,500 | 18.09 | 4.71/16 | 0.0054 | 3.391 | ad_saturated |
| Kiều Oanh Mê Làm Đẹp | 119,000 | 11.03 | 11.2/16 | 0.0372 | 0.019 | cold_channel |
| Tô Tuyết Trâm | 764,900 | 17.21 | 4.71/16 | 0.0053 | 0.242 | ad_saturated |
| Công chúa cam thường | 210,500 | 9.56 | 12.0/16 | 0.1769 | 0.015 | cold_channel, competitor_recent |
| Vàng Thị Solai | 756,100 | 16.03 | 4.2/16 | 0.0109 | 0.238 | ad_saturated |
| Mần đẹp 💅 | 785,700 | 13.68 | 5.37/16 | 0.0058 | 0.097 | ad_saturated |

**Đã đo bằng AI (live):** 14 video phân tích (frames + transcript ASR → LLM rubric, evidence từng quote/observation); lý do đề xuất **7/7 pass validator** bằng chứng; **dry-run numeric audit: 54/57 con số khớp trực tiếp trong `evidence_id` trích dẫn** (+3 khớp hồ sơ/evidence khác của cùng creator = **57/57** truy nguyên được, 0 số bịa); recall audit: 2 mẫu bị loại chấm lại → **0 miss**.

## 2. Token efficiency — chi phí đo thật

**Bảng tổng hợp theo tầng & provider (đo từ `usage_ledger`, 1cr Kalodata ≈ 0,1 USD tham khảo):**

| Tầng | Provider | Calls (lạnh) | Credit | Token in | Token out | AI USD | Avg ms/call | Cache hits (ấm) |
|---|---|---|---|---|---|---|---|---|
| s0 | kalodata | 1 | 0.1 | 0 | 0 | $0.0000 | 200 | 0 |
| s0 | llm | 1 | 0.0 | 6,453 | 506 | $0.0180 | 148535 | 0 |
| s1 | kalodata | 4 | 0.4 | 0 | 0 | $0.0000 | 2740 | 4 |
| s2a | kalodata | 30 | 3.0 | 0 | 0 | $0.0000 | 2275 | 30 |
| s2b | kalodata | 18 | 1.8 | 0 | 0 | $0.0000 | 813 | 18 |
| s3 | llm | 9 | 0.0 | 67,804 | 19,435 | $0.3300 | 66698 | 0 |
| s4 | asr | 28 | 0.0 | 0 | 0 | $0.0000 | 100957 | 0 |
| s4 | kalodata | 15 | 7.5 | 0 | 0 | $0.0000 | 239 | 0 |
| s4 | llm | 14 | 0.0 | 89,749 | 20,702 | $0.7730 | 29903 | 14 |
| s5 | llm | 7 | 0.0 | 139,902 | 46,826 | $0.7481 | 100015 | 0 |
| **Tổng lạnh** | **all** | **127** | **12.8** | **303,908** | **87,469** | **$1.8690** | | |

- **AI (đo thật):** 31 call · 303,908 token in / 87,469 out (cache 0) · **$1.869** · avg 60244ms/call. S3 batch 10–15/call, S4 chỉ top-K × 2 video, rubric cố định đầu prompt, schema đóng, mọi call ghi ledger.
- **Calibration đo bằng credit/balance trước/sau:** 6 call spike = đúng 1,0cr; call lỗi (501, 2017) không mất credit; balance 15,0 → 8,6 sau spike + 2 lần smoke (trace trong measurements.json).
- Đòn bẩy đã cài: phễu giảm ~97% call video đắt (500×5=2.500 → ~75); page_size 100 cùng giá 0,1cr; video/detail bỏ (ffprobe free); cache dùng lại S2a→S4; credit guard tự giảm video khi sắp vượt hạn mức.
- Failover thật đã kích hoạt: S5 sonnet timeout → fallback chain ghi ledger `UNAVAILABLE → fallback` (xem benchmark.md); prompt trim + timeout tăng → retry thành công, lý do LLM thật.


## 3. Scalability — thiết kế 50–500, demo 30

- Mọi tầng parameterized (`config/defaults.yaml`): demo N=30→15→7→5+2; scale đổi `candidates: 500, after_2a: 100, after_3: max(15, 5%N)` — kiến trúc không đổi.
- **Đơn giá Kalodata đo được** → ngoại suy N=500: 500×0,1 (video/rank) + 100×0,1 (detail) + 75×0,5 (video/url) + ~0,7 (rank/category) ≈ **98 credit ≈ 9,8 USD**; phần AI ngoại suy từ đơn giá S4 khi đo xong.
- Rate limit thật đã gặp và xử lý: code 2017 traffic control → backoff trong connector + token bucket 30 req/10s + 4 worker; 20 task fail lần 1 → resume retry thành công toàn bộ (xem mục 4).
- Song song: ThreadPoolExecutor IO/LLM/ASR pool riêng; SQLite WAL 1 writer; dedupe in-flight khóa cache → không trả tiền 2 lần cho call trùng.
- Cache TTL phân loại: khoảng ngày tuyệt đối = bất biến; category named-range = TTL 24h; video/url = không cache (link ký 5 phút).


## 4. Reliability — lưu tiến độ, phục hồi đo được

**Unit tests: 26 passed in 2.80s** — gồm: runner idempotent (item done không chạy lại), retry 3 lần rồi fail không chặn item khác, waiting backoff, stale-running reset, cache pays-once, judgement cache hit không cần key, strict schema, selector constraints.

**Sự cố thật đã phục hồi (không diễn tập):** smoke lần 1 dính rate limit 2017 → 20/30 task S2a fail. `reset_retryable_failed` + resume → 20 task chạy lại thành công. Bằng chứng không trả tiền hai lần: S2a lạnh = **30 call / 3.0 credit cho đúng 30 creator** (mỗi creator trả đúng 1 lần 0,1cr; các attempt fail không bị tính tiền).

**Checkpoint thật trong DB:**

| Stage | done | failed | waiting | pending |
|---|---|---|---|---|
| s1 | 5 | 0 | 0 | 0 |
| s2 | 1 | 0 | 0 | 0 |
| s2a | 30 | 0 | 0 | 0 |
| s2a_cut | 1 | 0 | 0 | 0 |
| s2b | 18 | 0 | 0 | 0 |
| s3 | 4 | 0 | 0 | 0 |
| s4 | 1 | 0 | 0 | 0 |
| s4_judge | 14 | 0 | 0 | 0 |
| s4_media | 14 | 0 | 0 | 0 |
| s5 | 1 | 0 | 0 | 0 |

- Kill -9 demo: `scripts/demo_resume.py` (spawn → kill giữa S2a → resume → so results.csv từng byte + chi phí thêm = 0) — chạy sau khi demo full hoàn tất, kết quả ghi `resume_demo.json` vào benchmark.
- Offline replay: fixtures + judgements bundle → người chấm chạy lại toàn pipeline không cần key/credit (`koc run --offline`).


## 5. Thời gian xử lý (đo từ ledger)

- s0 (`kalodata`): 1 call × avg 200ms = 0.2s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s0 (`llm`): 1 call × avg 148535ms = 148.5s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s1 (`kalodata`): 4 call × avg 2740ms = 11.0s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s2a (`kalodata`): 30 call × avg 2275ms = 68.2s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s2b (`kalodata`): 18 call × avg 813ms = 14.6s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s3 (`llm`): 9 call × avg 66698ms = 600.3s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s4 (`asr`): 28 call × avg 100957ms = 2826.8s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s4 (`kalodata`): 15 call × avg 239ms = 3.6s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s4 (`llm`): 14 call × avg 29903ms = 418.6s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- s5 (`llm`): 7 call × avg 100015ms = 700.1s tổng thời gian tác vụ (chạy song song nên wall-clock nhỏ hơn).
- ASR local: 28 video, tổng 2827s (0 USD, faster-whisper small int8).
- LLM: 31 call, tổng 1868s task-time (song song nên wall-clock nhỏ hơn).


## 6. Trạng thái hoàn thành

- ✅ Full pipeline S0→S5 chạy LIVE: AI phân tích brief, sàng lọc ngữ nghĩa, phân tích video (frames + ASR tiếng Việt), chọn bộ 5 + 2 dự phòng, lý do LLM trích bằng chứng.
- ✅ Validator: 7/7 lý do pass; recall audit 2 mẫu / 0 miss.
- ✅ Benchmark lạnh/ấm + kill/resume demo: xem `benchmark.md` + `resume_demo.json` (nếu đã chạy).
- Chưa làm (stretch có chủ đích, giải thích trong README/ARCHITECTURE D16): Jev judge, Google Sheets, Batch API (−50%), human baseline, LLM-as-judge, vòng phản hồi sau chiến dịch.
- Giới hạn dữ liệu (khán giả, giá thuê, mẫu video nhỏ, ER threshold, ASR noise): README mục Giới hạn — không giấu.


## 7. Cách tái lập

```bash
uv sync
uv run pytest -q                          # unit tests
uv run python scripts/export_test_report.py # xuất lại báo cáo này từ DB
uv run koc run --brief briefs/sunscreen.txt --run-id demo_sunscreen  # khi có LLM key
uv run koc run --offline --run-id replay_demo               # không cần key/credit
```
