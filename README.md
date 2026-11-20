# AI KOC Discovery

Hệ thống tìm và đề xuất KOC TikTok dựa trên **bằng chứng**, cho bài test Founding Engineer (DETOLA).
Brief ngôn ngữ tự nhiên → AI phân tích → phễu 5 tầng rẻ→đắt → bộ 5 KOC + 2 dự phòng trong ngân sách,
kèm lý do trích bằng chứng kiểm chứng được, danh sách loại kèm lý do, **dashboard HTML trực quan** và benchmark đo thật.

**Nguyên tắc:** chất lượng giải pháp, hiệu quả chi phí, tư duy kiến trúc > độ phức tạp.
Code lo số liệu và lựa chọn; AI chỉ xuất hiện ở chỗ cần phán đoán. Mọi lời gọi tốn tiền đi qua
một cửa có cache + ledger. Mọi tiến độ nằm trong SQLite — kill bất kỳ lúc nào, resume không trả tiền lại.

## Chạy nhanh

```bash
# 1. Cài (Python 3.12+, uv)
uv sync

# 2. Cấu hình key — copy .env.example thành .env rồi điền:
#    KALO_API_KEY=...            (Kalodata Open API)
#    LLM_BASE_URL=...            (bất kỳ endpoint OpenAI-compatible)
#    LLM_API_KEY=...
#    LLM_MODEL_SCREEN/VIDEO/REASON/BRIEF=...   (xem .env.example: Anthropic / Gemini / OpenRouter / local)

# 3. Chạy demo (mặc định 30 ứng viên → 5 KOC + 2 dự phòng)
uv run koc run --brief briefs/sunscreen.txt --open

# Kết quả xuất thống nhất tại 1 thư mục: reports/ (dashboard.html · report.md · results.csv · excluded.csv · benchmark.md)
```

**Kết quả test đã chạy (đọc ngay trên GitHub trong thư mục `reports/`, không cần chạy lại):**
- `reports/dashboard.html`: **báo cáo trực quan cho người kinh doanh — TỰ SINH mỗi lần `koc run/resume/report`** (`src/koc/dashboard.py`): thẻ KOC kèm bằng chứng, biểu đồ phễu/điểm/độ nhạy ngân sách, chi phí, kiểm chứng. Ngôn ngữ phi kỹ thuật, không chứa contact cá nhân, mở thẳng bằng browser.
- `reports/TEST-RESULTS.md`: tổng hợp theo 4 tiêu chí đề bài (chất lượng bằng chứng, token/chi phí đo thật, scalability, reliability kèm sự cố rate-limit thật đã phục hồi).
- `reports/report.md` & `reports/results.csv`: **báo cáo chi tiết 5 KOC chính thức + 2 dự phòng**, lý do đề xuất kèm mã `evidence_id`, phương án thay thế, ngân sách & giá trần (email/zalo cá nhân đã redact trong bản public).
- `reports/benchmark.md` & `reports/resume_demo.json`: bảng chi phí LẠNH/ẤM từ `usage_ledger`, ngoại suy $N=500$, và bằng chứng `kill -9 → resume` (`extra_credits = 0`, `verdict: PASS`).
- `reports/kept.csv` / `reports/excluded.csv` / `reports/measurements.json`: bảng ứng viên qua S2, danh sách loại kèm lý do, và số đo thô từ SQLite.
Xuất lại/cập nhật toàn bộ thư mục `reports/`: `uv run python scripts/export_test_report.py`.

### Đổi provider LLM — không sửa code

Mọi vai trò (`brief`, `screen`, `video`, `reason`) cấu hình độc lập `base_url`, `api_key`, `model`, `extra`
qua `.env` hoặc `config/defaults.yaml`. Ví dụ chuyển sang **Google Gemini** (qua OpenAI-compatible endpoint chính thức của Google AI Studio):

```bash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=...
LLM_MODEL_BRIEF=gemini-3.8-flash
LLM_MODEL_SCREEN=gemini-3.8-flash
LLM_MODEL_VIDEO=gemini-4-argon
LLM_MODEL_REASON=gemini-4-argon
```

Giá token tham chiếu để tính chi phí: `config/prices.yaml` (hỗ trợ sẵn dòng `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-5-5`, `gemini-4-argon`, `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.1-pro`, `gemini-3.1-flash-lite`; model lạ → ledger vẫn ghi đủ token, `cost=null`).

**Bảo mật:** chỉ điền key vào `.env` (gitignore). `.env.example` là template — KHÔNG điền key thật.

### Fallback khi LLM không gọi được (bounded, tường minh)

- **Chain dự phòng opt-in (cùng hoặc khác provider)**:
  - Toàn cục cho mọi tầng: đặt `LLM_FALLBACK_MODEL` (ví dụ `gemini-4-argon`), `LLM_FALLBACK_BASE_URL` (ví dụ `https://generativelanguage.googleapis.com/v1beta/openai/`), `LLM_FALLBACK_API_KEY`.
  - Hoặc riêng cho tầng tổng hợp lý do S5: `LLM_REASON_FALLBACK_MODEL` (ví dụ `claude-opus-5-5` hoặc `gemini-4-argon`).
  - Khi role chính lỗi (auth/quota/404/timeout/schema-invalid sau retry), hệ thống tự động chuyển sang fallback và ghi rõ vào `usage_ledger`: `UNAVAILABLE <primary_model> → fallback <fallback_model>`. Không khai báo = không fallback.
- **Không có router tự chọn model động** — lý do: phá cache judgement, phá determinism resume,
  phá attribution benchmark (xem `docs/ARCHITECTURE.md` D18). Phễu theo vai trò đã là routing chi phí.
- **Degrade, don't stop**: mọi provider fail → S0 dùng `campaign_defaults` YAML + keyword match
  (đánh dấu DEGRADED), S3 chấm phần code + cờ `screen_missing`, S4 giảm coverage, S5 sinh lý do
  template từ evidence thật (vẫn pass validator, ghi rõ "cần người viết lại"). Pipeline luôn ra
  deliverable với phần thiếu đánh dấu trung thực.

### Chạy lại OFFLINE & Dựng báo cáo (gồm Dashboard HTML) không cần key/credit

Repo kèm `fixtures/` (response Kalodata ghi từ chạy thật) + `fixtures/judgements_bundle.json`
(kết quả LLM đã cache). Chế độ replay đọc toàn bộ từ đó, không gọi mạng.
Mọi lệnh `run`, `resume`, `report` đều **tự động sinh đủ bộ báo cáo** vào `reports/` (`dashboard.html`, `report.md`, `results.csv`, `excluded.csv`, `benchmark.md`); thêm cờ `--open` để mở ngay `reports/dashboard.html` trên trình duyệt:

```bash
uv run koc run --offline --open            # chạy lại toàn bộ pipeline từ fixtures, 0 credit, 0 token, mở dashboard.html
uv run koc resume --offline --open         # tiếp tục run có sẵn ở chế độ offline
uv run koc report --open                   # chỉ dựng lại toàn bộ report (.html/.md/.csv) từ SQLite DB, không gọi API/LLM
uv run python scripts/export_test_report.py # xuất/cập nhật thêm TEST-RESULTS.md, kept.csv, measurements.json vào reports/
```

### Resume sau gián đoạn

```bash
uv run koc resume                      # mặc định demo_sunscreen (hoặc truyền <run_id>): task dở chạy lại (cache hit, 0đ)
uv run python scripts/demo_resume.py   # demo kill cứng giữa chừng → resume → đối chiếu kết quả + chi phí thêm (reports/resume_demo.json)
```

### Benchmark

```bash
uv run koc bench                       # chạy ấm lại toàn pipeline (cache giữ nguyên) → reports/benchmark.md tách LẠNH/ẤM
```

## Kiến trúc (tóm tắt — chi tiết + lý do từng quyết định: `docs/ARCHITECTURE.md`)

```
brief.txt → [S0] AI phân tích brief (grounded trên cây danh mục Kalodata thật)
          → [S1] creator/rank đa lát cắt + dedupe (INDEPENDENT, bỏ channel hãng)
          → [S2a] video/rank MỌI ứng viên → code chấm ER/median/view-follower/red flags → cắt
          → [S2b] creator/detail survivors (bio, contacts, follower spike)
          → [S3] LLM nhỏ sàng lọc ngữ nghĩa theo batch + recall audit mẫu bị loại
          → [S4] 2 video đại diện/creator (top bán + mới nhất, seeded)
                 → tải ngay (link ký 5 phút) → ffmpeg frames + faster-whisper transcript
                 → LLM đa phương thức chấm rubric → evidence từng quote/observation
          → [S5] duyệt tổ hợp C(K,5) code: ngân sách + slot + đa dạng
                 → LLM viết lý do TỪ evidence → validator từ chối lý do không nguồn
          → reports/: dashboard.html + report.md + results.csv + excluded.csv + benchmark.md
Ngang: SQLite WAL (runs·tasks·api_cache·judgements·evidence·videos·usage_ledger)
```

- **Token efficiency:** phễu giảm ~97% lời gọi video đắt so với làm ngây thơ; rubric cố định đầu
  prompt (provider auto-cache); schema đóng; batch S3; ledger đo từng token/credit.
- **Reliability:** task idempotent theo (run, stage, entity); cache và tiến độ tách riêng;
  kill -9 → resume chỉ làm lại phần dở; chi phí thêm cho phần đã xong = 0 (demo đo được).
- **Chất lượng:** điểm hiển thị **đã đo X/65** (khán giả 25đ + hợp tác 10đ không có dữ liệu →
  checklist xác minh, không đoán); mọi lý do trích `evidence_id` truy ngược về API gốc hoặc
  file video + timestamp; recall audit đo mức bỏ sót của phễu, báo cáo thẳng.

## Chi phí demo (đo thật bằng ledger, xem `reports/benchmark.md`)

Kalodata tính theo credit (1 credit ≈ 0,1 USD tham khảo). Demo 30 ứng viên ≈ 13 credit
(video/url chiếm phần lớn) + AI ≈ 1–2 USD tùy provider. Hạn mức credit cấu hình ở
`limits.credit_budget`; vượt → hệ thống tự giảm số video/creator (degrade, không dừng).

## Giới hạn hiện tại (nói thẳng)

1. **Không có dữ liệu khán giả (giới tính/tuổi) và giá thuê KOC** trong Kalodata → 35/100 điểm
   không tự chấm; ngân sách xử lý bằng bảng giá GIẢ ĐỊNH theo tier + độ nhạy + giá trần từng KOC.
   Kết quả không thay thế bước xin ảnh Analytics và báo giá thật (checklist + mẫu tin trong report).
2. `video/rank` thiên video có doanh thu (công cụ TMĐT); mẫu 2 video/creator là chỉ báo,
   report ghi rõ "đã xem n/N video". **Chọn mẫu video & Ngách fit**:
   - Trong run demo đã chạy, S4 chọn `top_selling + latest` nên một số KOC đa ngành rơi vào video ngoài ngách chống nắng. Hàm `_plan_videos` ở `s4_video.py` đã được nâng cấp ưu tiên video có tiêu đề khớp `niche_keywords` cho các lần chạy mới (nhưng vẫn giữ nguyên 14 video đã xử lý của run demo/bundle để bảo toàn đối chiếu credit/ledger; tiêu đề teencode không chứa từ khóa vẫn có thể hụt).
   - Ngách fit hiện là trọng số mềm, chưa gate cứng: KOC hiệu suất cao nhưng video mẫu lạc ngách vẫn có thể được chọn — lý do + checklist nói thẳng khoảng trống bằng chứng, yêu cầu xem thêm video đúng ngách trước khi chốt. Mở rộng: tăng trọng số semantic fit + gate niche_fit tối thiểu khi có thêm credit phân tích video.
3. Doanh thu/GMV là ước tính của Kalodata, không kiểm chứng độc lập.
4. Ngưỡng ER tuyệt đối 0,5% (theo bộ tiêu chí) có thể loại oan KOC thiên bán hàng
   (view cao, ít like) — recall audit đo và báo cáo mức này; ngưỡng chỉnh trong config.
5. ASR tiếng Việt (faster-whisper small, local, 0 USD): đã kiểm trên video review thật —
   nhận diện đúng nội dung, còn noise model small ("chai ampoule" → "trai ampou");
   transcript kém → confidence thấp + cờ, không âm thầm bỏ tiêu chí. Video nhạc nền → 0 segments (VAD).
6. Đối thủ do AI đề xuất khi brief không nêu — **giả định, cần thương hiệu xác nhận**.
7. Chưa làm (có chủ đích, xem ARCHITECTURE.md D16): Jev/TypeSafe judge, Google Sheets,
   Batch API (−50%), human baseline, LLM-as-judge, vòng phản hồi sau chiến dịch,
   đo chồng lấn khán giả thật. Chưa dựng Web Server / Admin Backend đa người dùng (hệ thống đã tự sinh `reports/dashboard.html` trực quan cho từng lần chạy; thiết kế mở rộng FastAPI + Admin Panel xem tại `docs/ARCHITECTURE.md` mục 6), không tự cào TikTok, không đoán tuổi/giới tính từ mặt,
   không kết luận pháp lý (chỉ gắn cờ cho người duyệt).

## Hướng mở rộng (chi tiết thiết kế: `docs/EXPANSION-ROADMAP.md`)

- **REST API & Web Admin Dashboard (Dual-Interface: CLI + FastAPI + Web UI):** bọc mỏng FastAPI (`src/koc/api.py`) trên cùng Core Engine và SQLite WAL; hỗ trợ chạy/tạm dừng (`cancel_event`)/resume trực tiếp trên trình duyệt, xem thanh tiến độ thời gian thực, mở drawer xem 6 frame ảnh + transcript từng KOC (xem chi tiết các endpoint trong `docs/EXPANSION-ROADMAP.md` Phần 1).
- **Tầng S6 — Tự động hóa liên hệ KOC & khép vòng chấm điểm 100/100 (Automated Outreach & Auto-Reselect Loop):**
  1. *Cá nhân hóa lời mời từ bằng chứng:* dùng `contacts` (S2b) + `verify_before_contract` (S5) + `evidence` video (S4) để sinh bản nháp Email/Zalo cá nhân hóa cho từng KOC.
  2. *Human-in-the-loop & Anti-ban Guard:* quản lý trạng thái `outreach_tasks` (`drafted → approved → sent → replied | timeout`), gửi qua Email API / TikTok Creator Marketplace / Zalo OA sau khi marketer duyệt.
  3. *Multimodal Inbox Parser (OCR ảnh Analytics):* AI đọc phản hồi báo giá và OCR ảnh chụp màn hình TikTok Analytics do KOC gửi để chấm tự động **25đ Khán giả + 10đ Hợp tác** (gắn nhãn `human-verified` tách biệt với `system-measured /65`).
  4. *Auto-Fallback & Reselect (`koc reselect`):* nếu báo giá thật vượt `price_ceiling_vnd` hoặc KOC từ chối/quá hạn 48h, tự động chạy lại bộ chọn tổ hợp S5 (0 credit, vài mili-giây) để đôn KOC `[DỰ PHÒNG]` lên thay thế.
- **Đối chiếu đa nguồn & Kiểm toán bình luận qua TikTok API (Tầng S3.5 — Multi-Source Cross-Verification, chỉ chạy cho Top-K cuối):**
  - *TikTok Creator Marketplace (TTCM) / TikTok Shop Partner (TSP) API:* lấy dữ liệu nhân khẩu học khán giả chính chủ (`% Nữ`, `% 18–30`, `% VN`) để chấm tự động **25/100 điểm Khán giả** (`ttcm-verified`).
  - *TikTok Public Feed API:* lấy thêm các video organic (không gắn giỏ hàng) để bù đắp thiên lệch thương mại của `video/rank` trên Kalodata và kiểm tra chéo các ca dị biệt số liệu (`er_anomaly`).
  - *Comment Sentiment & Buying Intent Audit:* lấy Top 50 bình luận của các video đại diện đưa qua LLM nhỏ (< $0.01 cho 15 KOC) để đo tỷ lệ hỏi mua thật (Buying Intent) và phát hiện bot seeding hoặc phản hồi tiêu cực về sản phẩm.
- **Scale 500+:** đổi `funnel.candidates: 500`, `after_2a: 100`, `after_3: max(15, 5%N)`; thêm credit Kalodata. Kiến trúc không đổi: mọi tầng parameterized, cache/resume/ledger giữ nguyên; chi phí ngoại suy từ đơn giá đo được (`reports/benchmark.md`).
- **Batch API Anthropic (−50%)** cho S3/S4 khi không cần latency; adapter native cho `cache_control` tường minh.
- **Jev judge** cho S3 closed-set questions (interface `Judge` đã tách; chỉ thêm khi có bộ mẫu kiểm thử tiếng Việt 30–50 nhãn).
- **Autonomous Agent (2-tier Supervisor + Per-KOC Investigator):** khi cần tự động mở rộng vòng tìm kiếm (S1↔S2) hoặc gọi thêm tool chuyên sâu (`comment/insight`, `product/detail`) theo nghi vấn từng KOC mà không làm nổ context window.
- **Vòng phản hồi:** nhập kết quả chiến dịch thật → hiệu chỉnh trọng số rubric.
- **Hạ tầng:** Postgres khi cần nhiều process ghi; queue ngoài khi cần phân tán.

## Cấu trúc repo

```
src/koc/          # config, db, ledger, kalodata, llm, prompts, evidence, scoring,
                  # select, video, runner, pipeline, report, dashboard, cli, stages/s0..s5
config/           # defaults.yaml (mọi tham số), prices.yaml
briefs/           # brief ngôn ngữ tự nhiên
fixtures/         # API responses + judgements bundle (offline replay)
scripts/          # spike.py, demo_resume.py (kill/resume), export_test_report.py, scrub_fixtures.py
tests/            # pytest (32 tests): scoring, off-niche damping, selector, runner, cache, schema, evidence, vision self-correction, dashboard
docs/             # đề bài gốc, bộ tiêu chí KOC, ARCHITECTURE.md (19 quyết định), EXPANSION-ROADMAP.md (API/Admin & S6 Outreach)
reports/          # thư mục duy nhất chứa toàn bộ báo cáo & kết quả xuất ra (dashboard.html, report.md, results.csv, benchmark.md...)
runs/             # lưu trữ ngầm dữ liệu vận hành (koc.db, media/, frames/, transcripts/ — gitignore)
```

## Kiểm thử

```bash
uv run pytest -q     # 32 tests (~3s): ER/median/red flags, coverage & off-niche damping, selector constraints,
                     # runner idempotency + backoff, cache pays-once, strict schema,
                     # judgement cache + offline replay, numeric claim audit, niche-first video planner,
                     # vision blind-gateway detection, dashboard
```
