# Kết quả test ngày 19/11/2026 — AI KOC Discovery

Thư mục này chứa toàn bộ kết quả chạy test THẬT (`S0 → S5`) với Kalodata + LLM + ASR tiếng Việt, cùng kết quả kiểm thử `kill -9 / resume` và unit tests, tổ chức theo 4 tiêu chí của đề bài DETOLA.

## Đọc file nào?

| File | Nội dung | Đọc khi |
|---|---|---|
| **dashboard.html** | **Dashboard trực quan cho người kinh doanh** — mở bằng browser: thẻ 5 KOC + 2 dự phòng (lý do, bằng chứng, việc cần xác minh), biểu đồ phễu/điểm/độ nhạy ngân sách, chi phí, độ tin cậy. Ngôn ngữ phi kỹ thuật, kèm bảng dự phòng. **Tự sinh từ data run** (`src/koc/dashboard.py`, gọi trong `koc run/resume/report`) — không phải file tĩnh | Muốn xem trực quan, trình bày cho người không đọc code — **BẮT ĐẦU TỪ ĐÂY** |
| **TEST-RESULTS.md** | Báo cáo tổng hợp theo 4 tiêu chí đề bài: chất lượng bằng chứng · token/chi phí · scalability · reliability · thời gian xử lý | Muốn hiểu kết quả tổng quan nhanh theo tiêu chí chấm |
| **report.md** | **Báo cáo chi tiết 5 KOC chính thức + 2 dự phòng**: phân tích brief (S0), bảng phễu, điểm đã đo/chưa đo, lý do đề xuất kèm mã `evidence_id`, phương án thay thế, ngân sách & giá trần, recall audit | Muốn đọc đề xuất KOC và đối chiếu bằng chứng |
| **results.csv** | Bảng 5 KOC + 2 dự phòng (mở bằng Excel/Google Sheets): điểm từng nhóm, giá giả định, giá trần, tóm tắt, cờ rủi ro (email/zalo đã redact khi commit public) | Muốn xem dạng bảng |
| **benchmark.md** | Bảng đo thật từ `usage_ledger` (tách LẠNH / ẤM theo từng tầng S0–S5), ngoại suy chi phí $N=500$ (phễu vs ngây thơ), và kết quả `kill -9 / resume` | Muốn kiểm tra Token Efficiency & Scalability |
| **resume_demo.json** | Bằng chứng chạy tự động `scripts/demo_resume.py`: kill cứng process giữa S2a → `koc resume` → `extra_credits = 0`, `results.csv` khớp 100% | Muốn kiểm chứng Reliability |
| **kept.csv** | 12 KOC vượt qua vòng S2 (điểm số liệu code trước khi vào LLM S3/S4) | Muốn xem danh sách trung gian sau bước lọc số liệu |
| **excluded.csv** | KOC bị loại ở S2, MỖI người kèm lý do và con số cụ thể | Muốn kiểm tra phễu lọc có minh bạch không |
| **measurements.json** | Toàn bộ số đo thô dạng JSON (ledger, tasks, evidence, trace balance credit) | Muốn kiểm chứng số liệu bằng máy |

## Trạng thái hoàn thành

- ✅ **Full Pipeline (`S0 → S5`) đã chạy thật:**
  - `S0`: AI phân tích brief tự nhiên → khớp danh mục `601602` ("Kem chống nắng cho da mặt").
  - `S1 → S2`: Lấy 30 ứng viên độc lập (`INDEPENDENT`) → chấm số liệu từ 100 video/kênh → giữ 12, loại 18 (có lý do từng người).
  - `S3`: LLM sàng lọc ngữ nghĩa theo batch + Recall Audit mẫu bị loại (2 mẫu, 0 miss) → giữ 7 KOC vào vòng video.
  - `S4`: Tải 14 video đại diện (2 video/KOC) → trích 6 frames + transcript `faster-whisper` tiếng Việt có timestamp → LLM đa phương thức chấm rubric.
  - `S5`: Duyệt tổ hợp chọn 5 KOC + 2 dự phòng trong ngân sách 30 triệu → LLM viết lý do từ kho bằng chứng → **7/7 KOC pass `validate_reason`**.
- 💰 **Tổng chi phí chạy lạnh (đo từ `usage_ledger`):** **12.8 Kalodata credits** + **$1.869 AI** (391,377 tokens). Chạy ấm / resume phần đã xong = **0 credit, $0.0000**.
- 🛡️ **Reliability:** Đã phục hồi tự động qua sự cố rate-limit thật (mã `2017`) không mất tiền 2 lần, và pass bài test `kill -9` giữa chừng (`verdict: PASS`).
- 🧪 **Unit tests:** 30 passed (~3s).

## Tái lập / cập nhật

```bash
uv run koc report --open                    # dựng lại báo cáo & mở dashboard.html
uv run python scripts/export_test_report.py # xuất lại toàn bộ các file trong reports/
```

Nguồn số liệu: `runs/demo_sunscreen/koc.db` (bảng `usage_ledger`, `tasks`, `evidence`) — không có số ước tính suông.
