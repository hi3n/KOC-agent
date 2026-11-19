# AI KOC Discovery

Hệ thống tìm và đề xuất KOC TikTok dựa trên **bằng chứng**, cho bài test Founding Engineer (DETOLA).
Brief ngôn ngữ tự nhiên → AI phân tích → phễu 5 tầng rẻ→đắt → bộ 5 KOC + 2 dự phòng trong ngân sách,
kèm lý do trích bằng chứng kiểm chứng được, danh sách loại kèm lý do, và benchmark đo thật.

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
uv run koc run --brief briefs/sunscreen.txt

# Kết quả: runs/<run_id>/report.md · results.csv · excluded.csv · benchmark.md
```

**Kết quả test đã chạy (đọc ngay trên GitHub, không cần chạy lại):** `reports/ket-qua-test-2026-11-19/` —
- `TEST-RESULTS.md`: tổng hợp theo 4 tiêu chí đề bài (chất lượng bằng chứng, token/chi phí đo thật, scalability, reliability kèm sự cố rate-limit thật đã phục hồi).
- `report.md` & `results.csv`: **báo cáo chi tiết 5 KOC chính thức + 2 dự phòng**, lý do đề xuất kèm mã `evidence_id`, phương án thay thế, ngân sách & giá trần (email/zalo cá nhân đã redact trong bản public).
- `benchmark.md` & `resume_demo.json`: bảng chi phí LẠNH/ẤM từ `usage_ledger`, ngoại suy $N=500$, và bằng chứng `kill -9 → resume` (`extra_credits = 0`, `verdict: PASS`).
- `kept.csv` / `excluded.csv` / `measurements.json`: bảng ứng viên qua S2, danh sách loại kèm lý do, và số đo thô từ SQLite.
Mỗi ngày chạy lại = một thư mục snapshot mới, không ghi đè kết quả cũ.
Xuất lại/cập nhật: `uv run python scripts/export_test_report.py`.

### Đổi provider LLM — không sửa code

Mọi vai trò (brief/screen/video/reason) cấu hình độc lập `base_url`, `api_key`, `model`, `extra`
qua env hoặc `config/defaults.yaml`. Ví dụ Gemini:

```bash
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_API_KEY=...
LLM_MODEL_SCREEN=gemini-2.5-flash
LLM_MODEL_VIDEO=gemini-2.5-pro
```

Giá token để tính chi phí: `config/prices.yaml` (sửa được; model lạ → ledger vẫn ghi token, cost=null).

**Bảo mật:** chỉ điền key vào `.env` (gitignore). `.env.example` là template — KHÔNG điền key thật.

### Fallback khi LLM không gọi được (bounded, tường minh)

- **Chain dự phòng opt-in**: đặt `LLM_FALLBACK_MODEL/BASE_URL/API_KEY` (provider khác cũng được)
  → mọi role fail (auth/quota/404/schema-invalid sau retry) tự chuyển fallback, ledger ghi rõ
  `UNAVAILABLE model → fallback model`. Không khai báo = không fallback.
- **Không có router tự chọn model động** — lý do: phá cache judgement, phá determinism resume,
  phá attribution benchmark (xem `docs/ARCHITECTURE.md` D18). Phễu theo vai trò đã là routing chi phí.
- **Degrade, don't stop**: mọi provider fail → S0 dùng `campaign_defaults` YAML + keyword match
  (đánh dấu DEGRADED), S3 chấm phần code + cờ `screen_missing`, S4 giảm coverage, S5 sinh lý do
  template từ evidence thật (vẫn pass validator, ghi rõ "cần người viết lại"). Pipeline luôn ra
  deliverable với phần thiếu đánh dấu trung thực.

### Chạy lại OFFLINE không cần key/credit (cho người chấm)

Repo kèm `fixtures/` (response Kalodata ghi từ chạy thật) + `fixtures/judgements_bundle.json`
(kết quả LLM đã cache). Chế độ replay đọc toàn bộ từ đó, không gọi mạng:

```bash
uv run koc run --offline --run-id replay_demo     # chạy lại từ đầu, 0 credit, 0 token
uv run koc resume demo_sunscreen --offline        # tiếp tục run có sẵn
uv run koc report demo_sunscreen                  # dựng lại report từ DB, không gọi gì
```

### Resume sau gián đoạn

```bash
uv run koc resume <run_id>     # task đang dở chạy lại (cache hit, 0 đồng); task xong giữ nguyên
uv run python scripts/demo_resume.py   # demo kill cứng giữa chừng → resume → so kết quả + chi phí thêm
```

### Benchmark

```bash
uv run koc bench <run_id>      # chạy ấm lại toàn pipeline (cache giữ nguyên) → benchmark.md tách LẠNH/ẤM
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
          → report.md + results.csv + excluded.csv + benchmark.md
Ngang: SQLite WAL (runs·tasks·api_cache·judgements·evidence·videos·usage_ledger)
```

- **Token efficiency:** phễu giảm ~97% lời gọi video đắt so với làm ngây thơ; rubric cố định đầu
  prompt (provider auto-cache); schema đóng; batch S3; ledger đo từng token/credit.
- **Reliability:** task idempotent theo (run, stage, entity); cache và tiến độ tách riêng;
  kill -9 → resume chỉ làm lại phần dở; chi phí thêm cho phần đã xong = 0 (demo đo được).
- **Chất lượng:** điểm hiển thị **đã đo X/65** (khán giả 25đ + hợp tác 10đ không có dữ liệu →
  checklist xác minh, không đoán); mọi lý do trích `evidence_id` truy ngược về API gốc hoặc
  file video + timestamp; recall audit đo mức bỏ sót của phễu, báo cáo thẳng.

## Chi phí demo (đo thật bằng ledger, xem `runs/*/benchmark.md`)

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
   đo chồng lấn khán giả thật. Không UI, không tự cào TikTok, không đoán tuổi/giới tính từ mặt,
   không kết luận pháp lý (chỉ gắn cờ cho người duyệt).

## Hướng mở rộng

- **Scale 500:** đổi `funnel.candidates: 500`, `after_2a: 100`, `after_3: max(15, 5%N)`;
  thêm credit Kalodata. Kiến trúc không đổi: mọi tầng parameterized, cache/resume/ledger giữ nguyên;
  chi phí ngoại suy từ đơn giá đo được (benchmark.md).
- **Batch API Anthropic (−50%)** cho S3/S4 khi không cần latency; adapter native cho cache_control tường minh.
- **Jev judge** cho S3 closed-set questions (interface `Judge` đã tách; chỉ thêm khi có bộ mẫu
  kiểm thử tiếng Việt 30–50 nhãn).
- **Giá thật & Analytics thật (`koc reselect` hướng mở rộng):** ghi đè báo giá thật + điểm khán giả xác minh từ ảnh Analytics (gắn nhãn `human-verified` tách biệt với `system-measured /65`, lưu provenance) → chạy lại S5 và chỉ sinh lại lý do cho thành viên thay đổi.
- **Autonomous Agent (2-tier Supervisor + Per-KOC Investigator):** khi cần tự động mở rộng vòng tìm kiếm (S1↔S2) hoặc gọi thêm tool chuyên sâu (`comment/insight`, `product/detail`) theo nghi vấn từng KOC mà không làm nổ context window.
- **Vòng phản hồi:** nhập kết quả chiến dịch thật → hiệu chỉnh trọng số rubric.
- Postgres khi cần nhiều process ghi; queue ngoài khi cần phân tán.

## Cấu trúc repo

```
src/koc/          # ~1.800 dòng: config, db, ledger, kalodata, llm, evidence, scoring,
                  # select, video, runner, pipeline, report, cli, stages/s0..s5
config/           # defaults.yaml (mọi tham số), prices.yaml
briefs/           # brief ngôn ngữ tự nhiên
fixtures/         # API responses + judgements bundle (offline replay)
scripts/          # spike.py, demo_resume.py (kill/resume), export_test_report.py, scrub_fixtures.py
tests/            # pytest: scoring, selector, runner idempotency, cache, schema, evidence
docs/             # đề gốc, tiêu chí, ARCHITECTURE.md (chốt), REVIEW-AND-API-DASHBOARD.md (UNUSED/: lịch sử bản nháp)
runs/             # per-run: koc.db, media/, frames/, transcripts/, report (gitignore)
```

## Kiểm thử

```bash
uv run pytest -q     # 26 tests (~3s): ER/median/red flags, coverage, selector constraints,
                     # runner idempotency + backoff, cache pays-once, strict schema,
                     # judgement cache + offline replay, numeric claim audit, niche-first video planner
```
