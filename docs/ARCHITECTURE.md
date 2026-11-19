# Kiến trúc Hệ thống AI KOC Discovery

Tài liệu này trình bày sơ đồ kiến trúc, cấu trúc module, giao thức đảm bảo độ tin cậy (Reliability) và giải thích chi tiết **19 quyết định thiết kế cốt lõi (D1–D19)** của hệ thống **AI KOC Discovery**.

**Nguyên tắc thiết kế chủ đạo:** *Chất lượng giải pháp, hiệu quả chi phí và tư duy kiến trúc được ưu tiên hơn độ phức tạp của hệ thống.*
- **Phân định rõ trách nhiệm Code vs. AI:** Code xử lý các phép tính thống kê, kiểm tra ràng buộc ngân sách và duyệt tổ hợp tất định; AI chỉ được gọi ở những bước đòi hỏi phán đoán ngữ nghĩa, thị giác và tổng hợp lập luận dựa trên bằng chứng.
- **Provider-neutral:** Không phụ thuộc cứng vào một nhà cung cấp LLM; mọi vai trò (`brief`, `screen`, `video`, `reason`) đều cấu hình độc lập `base_url`, `api_key`, `model` qua biến môi trường hoặc YAML.
- **Cost & Progress Accounting:** Mọi lời gọi tốn chi phí (Kalodata API, LLM) đều đi qua tầng cache + sổ cái (`usage_ledger`). Trạng thái từng tác vụ lưu trong SQLite WAL, cho phép dừng đột ngột (`kill -9`) và chạy tiếp (`resume`) mà không tốn lại chi phí cho phần việc đã hoàn tất.

---

## 1. Sơ đồ Kiến trúc Tổng thể

```
brief.txt (ngôn ngữ tự nhiên)
   │
   ▼
[S0] category/rank (cache) ─┐
     brief + cây danh mục ──┴─► LLM (role=brief) → BriefAnalysis (pydantic)
                                → validate ID/budget → RunConfig + config_hash, seed
   ▼
[S1] creator/rank đa lát cắt (revenue/views/growth/nano) + dedupe (INDEPENDENT)
   ▼
[S2a] video/rank mỗi creator (0,1cr) → code: ER, median/mean,
      view/follower, tần suất, red flags, niche keyword
      ↳ excluded.csv + lý do từng KOC; mẫu ~10% chấm lại S3 (recall audit)
   ▼
[S2b] creator/detail các ứng viên vượt S2a (bio, top products, follower spike)
   ▼
[S3] LLM (role=screen, model nhỏ) chấm theo batch: độ khớp ngách, đối thủ, rủi ro
   ▼
[S4] chọn 2 video đại diện/creator (seeded, ưu tiên khớp từ khóa ngách)
     → video/url (0,5cr) → tải ngay (link ký có thời hạn ngắn)
     → ffmpeg trích 6 frames (2 frames trong 3s đầu bắt hook) + faster-whisper transcript
     → LLM (role=video, đa phương thức) chấm rubric
     → lưu kho bằng chứng (evidence): metric | transcript_quote | frame_obs
   ▼
[S5] duyệt tổ hợp C(K,5) bằng code: ràng buộc slot + ngân sách ≤ 30tr + đa dạng
     → top 3 phương án, phân tích độ nhạy giá (max_price_scale), giá trần, 2 dự phòng
     → LLM (role=reason) viết lý do từ kho evidence → validator + numeric claim audit
   ▼
report.md + results.csv + excluded.csv + benchmark.md (+ dashboard.html)

Tầng lưu trữ ngang: SQLite WAL (runs · tasks · api_cache · judgements · evidence · videos · usage_ledger)
                    Disk: runs/<run_id>/media/, frames/, transcripts/ (content-addressed)
```

---

## 2. Các Quyết định Thiết kế Chính (D1–D19)

| # | Quyết định | Lý do cụ thể | Đánh đổi chấp nhận |
|---|---|---|---|
| **D1** | **Phễu 5 tầng rẻ → đắt:** `rank` → `stats (code)` → `text (LLM nhỏ)` → `video (LLM đa phương thức, top-K)` → `chọn tổ hợp (code)` | Phân tích video là bước đắt nhất (~$0.055 LLM + 0.5 credit Kalodata ≈ $0.105/video). Làm ngây thơ cho 500 KOC × 5 video = 2.500 video tốn ~$273; dùng phễu chỉ phân tích video của nhóm top-K cuối cùng, **giảm ~95–97% chi phí** mà không giảm chất lượng của tập được chọn. | KOC bị loại sớm ở tầng 2 không được xem video → kiểm soát rủi ro bỏ sót bằng cơ chế **Recall Audit** (D12). |
| **D2** | **Code tính điểm số liệu, AI chỉ phán đoán nội dung** | Các chỉ số thống kê (ER, median view, view/follower, độ ổn định) hoàn toàn tất định, miễn phí và truy nguyên được về dữ liệu gốc. Dùng LLM để tính số học vừa tốn token vừa dễ sai số và không tái lập được. | AI vẫn cần cho ngữ nghĩa tiếng Việt (độ khớp ngách, sắc thái quảng cáo, kiểm tra kiến thức SPF/PA trong lời nói). |
| **D3** | **S0: AI phân tích brief ngôn ngữ tự nhiên, grounded trên cây danh mục thật của Kalodata** | Brief văn bản tự do được chuyển thành schema Pydantic (`BriefAnalysis`: sản phẩm, `category_ids`, `niche_keywords`, khán giả mục tiêu, `objective`, đối thủ, ngân sách). Danh sách danh mục lấy từ `category/rank` được đưa trực tiếp vào prompt để AI **chỉ chọn ID có thật**, sau đó code kiểm tra lại ID và ngân sách. | Tốn 1 lời gọi LLM (~$0.018), được cache theo hash(`brief + prompt + model`). Có cơ chế fallback về `campaign_defaults` khi chạy offline hoặc mất kết nối LLM. |
| **D4** | **Tầng LLM OpenAI-compatible dùng 1 client duy nhất, cấu hình độc lập theo từng vai trò (`role`)** | Chuẩn `chat/completions` tương thích với Anthropic, Google Gemini, OpenRouter và local gateway (vLLM/Ollama/LiteLLM). Đổi provider hoặc đổi model cho từng tầng chỉ cần sửa `.env` hoặc `config/defaults.yaml`, **không cần sửa code**. | Chưa dùng riêng tính năng `cache_control` đặc thù hay Batch API native của từng hãng; đổi lại giữ được mã nguồn gọn (~150 dòng) và hoàn toàn độc lập nhà cung cấp. |
| **D5** | **Structured Output nghiêm ngặt:** `response_format=json_schema` (strict) → fallback `json_object` + Pydantic validation + retry ≤ 2 | Mức hỗ trợ JSON schema của mỗi provider khác nhau; cơ chế tự động hạ cấp về `json_object` kết hợp kiểm tra Pydantic giúp giữ tính tương thích đa nền tảng mà vẫn đảm bảo đầu ra đóng, máy đọc và ghép điểm chính xác. | Có thể phát sinh thêm call retry nếu model yếu về định dạng schema (mọi lần retry đều được ghi nhận minh bạch vào `usage_ledger`). |
| **D6** | **Lưu trữ bằng SQLite WAL (1 file/run, 1 connection + RLock)** | Zero-deploy, người chấm chỉ cần chạy `uv run` không cần cài đặt DB server. Tách riêng bảng `api_cache` / `judgements` (dữ liệu đã trả tiền) khỏi bảng `tasks` (trạng thái tiến độ) giúp việc `resume` chỉ đơn giản là chạy tiếp các task chưa `done`. | Kiến trúc single-writer (phù hợp cho 1 tiến trình đa luồng); khi cần mở rộng đa tiến trình phân tán có thể chuyển sang PostgreSQL. |
| **D7** | **Đồng thời hóa bằng `ThreadPoolExecutor` (tách riêng pool IO/LLM và pool ASR)** | Các thư viện `httpx`, `openai` SDK và `faster-whisper` đều hoạt động ổn định ở chế độ đồng bộ; dùng thread pool tách biệt giữa tác vụ mạng (IO-bound) và tác vụ bóc băng âm thanh (CPU-bound) giúp kiểm soát tài nguyên gọn nhẹ và tránh nghẽn cổ chai. | Không tối ưu tới mức hàng nghìn kết nối đồng thời như `asyncio`, nhưng vượt xa ngưỡng rate-limit thực tế của Kalodata API. |
| **D8** | **S2a: Gọi `video/rank` cho toàn bộ ứng viên (0,1 credit/call) trước khi cắt phễu** | Để tính chính xác ER trung vị, tỷ lệ `median/mean view`, `view/follower`, tần suất đăng bài và phát hiện cờ đỏ, hệ thống cần thống kê trên danh sách video của từng KOC (thông tin mà `creator/detail` không có). Dữ liệu này được cache lại và tái sử dụng ở tầng S4 với chi phí 0 credit. | Endpoint `video/rank` của Kalodata có xu hướng ưu tiên video thương mại; hệ thống lấy tối đa `page_size=100` (cùng mức phí 0,1 credit) rồi tự sắp xếp theo thời gian đăng ở phía client. |
| **D9** | **Không dùng bộ lọc `engagement_rate` dựng sẵn của Kalodata ở S1** | Thang phân loại ER của Kalodata (`LOW < 8%`, `MEDIUM`, `HIGH > 20%`) khác bản chất với công thức ER tiêu chuẩn ngành `((like + comment + share) / view`, ngưỡng sàn `0,5%`). Trộn hai định nghĩa sẽ dẫn đến loại nhầm KOC tiềm năng mà không giải thích được. | Tầng S1 lấy ứng viên theo đa lát cắt (doanh thu, lượt xem, tốc độ tăng trưởng, nhóm nano), sau đó tầng S2a tự tính ER chuẩn hóa từ dữ liệu video. |
| **D10** | **Phân tích đa phương thức ở S4:** Tải video ngay → trích 6 frames JPEG (2 frames trong 3 giây đầu) + transcript `faster-whisper` tiếng Việt có timestamp | Để đánh giá tiêu chí *"kiến thức chống nắng (SPF/PA, thoa lại) chính xác"* và *"âm thanh rõ"*, chỉ nhìn ảnh là không đủ. Chạy ASR local bằng `faster-whisper` (`small`, `int8`) tốn **$0 chi phí API** và tạo ra bản gỡ băng kèm timestamp làm bằng chứng trích dẫn trực tiếp. | Với video chỉ ghép nhạc nền hoặc âm thanh nhiễu, ASR sẽ trả về ít/không có đoạn thoại (hệ thống tự động hạ điểm tin cậy `confidence` và gắn cờ cho người duyệt, không suy diễn). |
| **D11** | **Chọn 2 video đại diện/KOC ở S4 (`top_selling` + `latest`), ưu tiên video khớp từ khóa ngách** | Cân bằng giữa độ phủ (*video bán tốt nhất* + *phong cách hiện tại*) và chi phí credit/LLM. Bộ chọn video ưu tiên các video có tiêu đề khớp `niche_keywords` của chiến dịch; đồng thời báo cáo luôn công bố minh bạch tỷ lệ *"Đã xem n/N video"*. | Mẫu 2 video/KOC là chỉ báo đại diện; với các KOC đa ngành chưa có video đúng ngách trong mẫu, báo cáo sẽ gắn cờ yêu cầu kiểm tra thêm trước khi ký hợp đồng. |
| **D12** | **Bằng chứng là thực thể hạng nhất (`evidence` table) + Validator đối chiếu nguồn + Recall Audit 10%** | Mọi con số, câu trích lời nói hay quan sát khung hình đều được cấp mã `evidence_id` lưu trong DB. Lý do đề xuất ở S5 bắt buộc trích dẫn `evidence_id` hợp lệ; bộ `validate_reason` và `audit_numeric_claims` kiểm tra chéo từng con số với dữ liệu gốc. Ngoài ra, lấy mẫu ~10% KOC bị loại ở S2a đưa qua S3 chấm lại để đo tỷ lệ bỏ sót. | Tốn thêm một lượng nhỏ token ở tầng S3 cho mẫu Recall Audit, đổi lại chứng minh được độ an toàn của phễu lọc bằng số liệu thực nghiệm. |
| **D13** | **S5: Chọn bộ 5 KOC bằng thuật toán duyệt tổ hợp tất định $\binom{K}{5}$; LLM chỉ viết lời giải thích** | Các ràng buộc cứng (tổng ngân sách ≤ 30 triệu VNĐ, cơ cấu vai trò Anchor/Mid/Micro, chống trùng lặp cụm nội dung) phải được đảm bảo tuyệt đối. Thuật toán duyệt toàn bộ tổ hợp hợp lệ tìm ra nghiệm tối ưu toàn cục trong vài mili-giây, đồng thời xuất được Top 3 phương án và độ chênh lệch điểm khi hoán đổi từng vị trí. | Khi số lượng ứng viên vòng cuối $K$ tăng rất lớn ($K > 50$), có thể chuyển từ duyệt vét cạn sang quy hoạch nguyên (ILP / Branch-and-Bound) với cùng hàm mục tiêu. |
| **D14** | **Mô hình hóa ngân sách bằng Bảng giá giả định theo Tier + Phân tích độ nhạy (`price_sensitivity`) + Giá trần từng KOC** | Kalodata không có dữ liệu báo giá booking thực tế của từng KOC. Hệ thống tách biệt hoàn toàn giá giả định khỏi điểm chất lượng (65đ), sau đó chạy mô phỏng các hệ số trượt giá (`0.7x` → `1.5x`) và tính **giá trần tối đa** cho từng KOC để marketer có quy tắc thương lượng rõ ràng: *báo giá thật vượt trần → chuyển sang KOC dự phòng cùng phân khúc*. | Các con số ngân sách trong báo cáo là mô hình tham chiếu theo phân khúc follower, không thay thế bước xin báo giá thực tế. |
| **D15** | **Benchmark đo lường thực tế từ `usage_ledger`** | Mọi chỉ số trong `benchmark.md` đều trích xuất trực tiếp từ sổ cái SQLite: tách biệt lần chạy **LẠNH** (gọi API thật) và lần chạy **ẤM** (cache hit), so sánh chi phí phễu với phương pháp ngây thơ từ đơn giá thực đo, kiểm chứng `kill -9 / resume` và tỷ lệ khớp bằng chứng. | Không dùng số ước tính cảm tính; các hạng mục đánh giá cảm quan của con người (Human Baseline) được đặt ở lộ trình mở rộng. |
| **D16** | **Giới hạn phạm vi có chủ đích (Scope Discipline)** | Chủ động không đưa vào các thành phần làm tăng độ phức tạp nhưng ít đóng góp cho mục tiêu cốt lõi của bài toán: không dùng bộ phân loại đóng Jev (vì chi phí tầng S3 với model nhỏ đã rất thấp và cần linh hoạt ngữ nghĩa tiếng Việt), không tích hợp Google Sheets OAuth, không tự cào trực tiếp TikTok ngoài Kalodata. | Mọi hạng mục chưa triển khai đều được giải thích rõ lý do và hướng mở rộng trong tài liệu. |
| **D17** | **Cơ chế Record / Replay (`fixtures/` + `judgements_bundle.json`) cho phép chạy `--offline`** | Toàn bộ phản hồi Kalodata (đã ẩn thông tin liên hệ cá nhân nhạy cảm) và kết quả đánh giá LLM được đóng gói kèm repo. Người chấm bài có thể chạy `uv run koc run --offline` để kiểm tra toàn bộ luồng xử lý từ S0 đến S5 mà **không cần API key và tốn 0 credit/token**. | Cần bước `scrub_fixtures.py` để làm sạch dữ liệu liên hệ cá nhân trước khi lưu vào kho mã nguồn công khai. |
| **D18** | **Cơ chế Failover tường minh & Hạ cấp an toàn (Graceful Degradation), không dùng Dynamic Model Router** | Không dùng bộ định tuyến tự động đổi model ngẫu nhiên theo độ khó vì sẽ làm vỡ khóa cache `judgements`, mất tính tất định khi `resume` và làm sai lệch số liệu quy thuộc trong benchmark. Thay vào đó, hệ thống dùng chuỗi dự phòng tường minh (`primary → fallback`) chỉ kích hoạt khi gặp lỗi thực sự, và nếu mọi provider đều lỗi thì hạ cấp an toàn theo từng tầng (đánh dấu `DEGRADED` trung thực trong báo cáo). | Khi chuyển sang model dự phòng, thang chấm có thể chênh lệch nhẹ — sổ cái `usage_ledger` luôn ghi rõ model thực tế đã sử dụng cho từng tác vụ. |
| **D19** | **Kiến trúc Bounded Agentic Funnel thay vì Unbounded ReAct Loop** | Ở quy mô hàng trăm KOC, một vòng lặp ReAct tự do dễ làm phình ngữ cảnh (context bloat), không đảm bảo tính tất định khi khôi phục sau sự cố (`kill -9 / resume`) và gây mất hiệu lực cache dây chuyền. Hệ thống sử dụng luồng điều phối có cấu trúc `S0 → S5` kết hợp các vòng tự sửa lỗi có giới hạn chặt (schema validation retry ≤ 2, evidence validator retry ≤ 1). | Khi cần tự động quay lại mở rộng vùng tìm kiếm hoặc đào sâu thêm bình luận cho riêng một số KOC nghi vấn, có thể nâng cấp theo mô hình 2 tầng (Supervisor + Per-KOC Investigator) ở phần hướng mở rộng. |

---

## 3. Cấu trúc Mã nguồn (`src/koc/`)

```
src/koc/
  config.py      # Nội suy biến môi trường ${VAR:-default}, Pydantic RunConfig, merge YAML + BriefAnalysis, config_hash
  db.py          # SQLite WAL schema (7 bảng), RLock, transaction context, khôi phục stale running → pending
  ledger.py      # Ghi nhận usage_ledger (credits, tokens, cost_usd, latency_ms) và tổng hợp số liệu benchmark
  kalodata.py    # Kalodata Open API client: persistent cache, token-bucket rate limiter, retry backoff mã 2017, record/replay
  llm.py         # OpenAI-compatible client theo từng role, json_schema → json_object fallback, judgement cache, failover chain
  prompts.py     # Hệ thống prompt và rubric cố định đầu prefix (tối ưu auto prompt-caching), chống prompt injection từ dữ liệu KOC
  evidence.py    # Kho lưu trữ bằng chứng content-addressed, bộ kiểm tra validate_reason và audit_numeric_claims
  scoring.py     # Tính toán ER, median/mean view, view/follower, độ ổn định, cờ đỏ (red flags) và điểm thành phần bằng code
  select.py      # Duyệt tổ hợp C(K,5) theo ràng buộc ngân sách + phân khúc + đa dạng, phân tích độ nhạy giá và giá trần
  video.py       # Tải video MP4, băm SHA-256, trích xuất khung hình qua ffmpeg, bóc băng tiếng Việt qua faster-whisper
  runner.py      # StageRunner đa luồng, đảm bảo tính idempotent theo (run_id, stage, entity_id) và xử lý backoff
  pipeline.py    # Khởi tạo ngữ cảnh Ctx, khôi phục cấu hình khi resume và điều phối luồng S0 → S5
  report.py      # Xuất báo cáo Markdown, CSV (results.csv, excluded.csv), benchmark.md và gọi sinh dashboard.html
  dashboard.py   # Tự sinh giao diện báo cáo trực quan reports/dashboard.html (biểu đồ phễu, điểm số, độ nhạy ngân sách)
  cli.py         # Giao diện dòng lệnh Typer: run, resume, report, bench, export-bundle (hỗ trợ --open mở dashboard)
  stages/        # 6 tầng xử lý độc lập: s0_brief, s1_candidates, s2_metrics, s3_screen, s4_video, s5_select
```

---

## 4. Giao thức Đảm bảo Độ tin cậy (Reliability) & Tính Tất định khi Phục hồi

1. **Đơn vị tác vụ Idempotent:**
   - Mỗi đơn vị công việc được định danh duy nhất bởi bộ khóa `(run_id, stage, entity_id)` trong bảng `tasks` với vòng đời: `pending → running → done | failed | waiting_kalodata`.
   - Khi khởi động lại hoặc gọi `koc resume <run_id>`, hệ thống tự động chuyển các tác vụ bị treo ở trạng thái `running` (do tiến trình trước bị ngắt đột ngột) và các lỗi mạng tạm thời (`2017` traffic control / lỗi kết nối) về lại `pending`.
2. **Tách biệt Lưu trữ Chi phí và Trạng thái Tiến độ:**
   - Mọi phản hồi từ Kalodata API được nén `zlib` và ghi vào bảng `api_cache` ngay khi nhận; mọi kết quả phán đoán của LLM được ghi vào bảng `judgements` trước khi đánh dấu task là `done`.
   - Nếu tiến trình bị `kill -9` ngay giữa thời điểm vừa gọi API xong nhưng chưa kịp cập nhật trạng thái task, lần chạy `resume` tiếp theo sẽ đọc trực tiếp từ `api_cache` / `judgements` (**cache hit = 0 credit, 0 token, $0 chi phí tăng thêm**).
3. **Tính Tất định Chuẩn hóa (Canonical Determinism):**
   - Để đảm bảo kết quả đầu ra sau khi `kill -9 / resume` giống hệt 100% so với một lần chạy liền mạch, mọi truy vấn đọc kết quả trung gian đều cố định thứ tự chuẩn (`ORDER BY entity_id`), việc chia lô ở tầng S3 sắp xếp theo `creator_id`, kho bằng chứng tự động khử trùng lặp theo `(kind, source_ref)`, và bộ chọn tổ hợp S5 sử dụng khóa phá hòa (tie-break) toàn phần kèm `random.Random(seed)` cố định.
4. **Bảo vệ Hạn mức Chi phí (Credit Budget Guard):**
   - Trước khi gọi API lấy link tải video ở tầng S4 (0,5 credit/video), hệ thống kiểm tra tổng số credit đã tiêu thụ trong `usage_ledger` so với `limits.credit_budget` (chỉ tính các video chưa có trong bộ nhớ đệm). Nếu sắp chạm trần, hệ thống chủ động giảm số video tải mới trên mỗi KOC và ghi nhận minh bạch vào báo cáo thay vì dừng đột ngột.

---

## 5. Các Phát hiện Thực nghiệm & Tối ưu Hóa Kỹ thuật Đã Triển khai

Trong quá trình kiểm thử trực tiếp với dữ liệu thực tế từ Kalodata Open API và pipeline xử lý video tiếng Việt, hệ thống đã giải quyết các bài toán kỹ thuật thực tế sau:

- **Loại bỏ cửa hàng thương hiệu (Brand Stores) khỏi danh sách KOC:** Trên Kalodata, các tài khoản có doanh thu cao nhất trong một ngành hàng thường là kênh bán hàng chính thức của nhãn hàng (`BELONGED_TO_SELLER`). Tầng S1 chủ động lọc `creator_type=INDEPENDENT` và tầng S2b kiểm tra chéo lại trạng thái kênh để chỉ đề xuất nhà sáng tạo nội dung độc lập.
- **Xử lý giới hạn lưu lượng (Traffic Control mã `2017`):** Kalodata trả thông báo vượt ngưỡng gọi API qua mã lỗi `2017` bên trong JSON envelope (thay vì HTTP 429) và không trừ credit cho các lệnh lỗi này. Client đã tích hợp bộ giới hạn tốc độ Token Bucket kết hợp cơ chế tự động lùi thời gian chờ (exponential backoff).
- **Xử lý dữ liệu thống kê dị biệt (Metric Anomalies):** Một số video trên Kalodata có lượt tương tác lớn hơn lượt xem ước tính (khiến ER > 100%). Bộ chấm điểm `scoring.py` tự động giới hạn trần ER khi tính điểm để không làm lệch phân phối, đồng thời giữ nguyên giá trị thô trong kho bằng chứng và gắn cờ `er_anomaly` / `er_unusually_high` để minh bạch với người duyệt.
- **Pipeline xử lý âm thanh độc lập PyAV trên Windows:** Để tránh xung đột phụ thuộc biên dịch C++ của thư viện `av` giữa các phiên bản Python trên Windows, `video.py` giải mã âm thanh trực tiếp qua `ffmpeg` ra luồng WAV 16kHz mono chuẩn hóa rồi chuyển thành mảng `numpy.float32` đưa thẳng vào `faster-whisper`, đảm bảo chạy ổn định trên mọi môi trường.
- **Tương thích Replay đa cấu hình (`--offline`):** Ở chế độ `--offline`, nếu người chấm không cấu hình biến môi trường `.env` giống hệt lúc ghi bundle (ví dụ khác tiền tố định tuyến của gateway), `LLMClient` tự động đối chiếu fallback theo bộ khóa bất biến `(prompt_version, rubric_version, state_hash)` để tái lập chính xác 100% kết quả mà không cần gọi mạng.

---

## 6. Hướng Mở rộng lên REST API & Admin Dashboard (Dual-Interface)

Kiến trúc hiện tại đã tách biệt hoàn toàn **Core Engine** (`src/koc/`) và tầng lưu trữ **SQLite WAL** khỏi giao diện dòng lệnh (`cli.py`), do đó có thể mở rộng trực tiếp thành kiến trúc hai giao diện (**CLI + FastAPI + Web Admin Dashboard**) mà không cần thay đổi logic xử lý lõi:

```
                 ┌───────────────────────────┐
                 │   Admin Panel / Dashboard │ (Web UI: HTML/JS hoặc React)
                 └─────────────┬─────────────┘
                               │ REST API / SSE
         ┌───────────┐   ┌─────▼─────────┐
         │ CLI       │   │ FastAPI       │ (Thin wrapper gọi Core Engine)
         │ (typer)   │   │ (api.py)      │
         └─────┬─────┘   └─────┬─────────┘
               │               │
               ▼               ▼
┌─────────────────────────────────────────────────────┐
│           KOC Discovery Core Engine                 │
│     (stages S0 -> S5, scoring, select, llm)         │
└──────────────────────────┬──────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────┐
│  SQLite (WAL Mode) + Disk (runs/<id>/frames,videos) │
└─────────────────────────────────────────────────────┘
```

- **Theo dõi tiến độ thời gian thực:** Chế độ SQLite WAL cho phép tiến trình worker ghi trạng thái vào bảng `tasks` và `usage_ledger` trong khi FastAPI đọc đồng thời qua endpoint `GET /api/runs/{id}/status` để hiển thị thanh tiến độ, biểu đồ phễu lọc và chi phí theo thời gian thực.
- **Truy xuất trực tiếp bằng chứng hình ảnh & âm thanh:** Các đường dẫn khung hình (`frames_json`) và bản gỡ băng có timestamp (`transcript_path`) đã được lưu có cấu trúc trong bảng `videos` và `evidence`, cho phép giao diện Web mở ngăn chi tiết (drawer) hiển thị trực tiếp các frame cắt từ video TikTok cùng câu thoại đối chiếu.
- **Cập nhật báo giá & số liệu khán giả thực tế (`koc reselect`):** Khi marketer nhận được ảnh chụp TikTok Analytics và báo giá thực từ KOC, chỉ cần cập nhật hai thông số này (gắn nhãn `human-verified` tách biệt với điểm `system-measured /65`) và chạy lại tầng S5 để hệ thống tính lại tổ hợp tối ưu trong vài giây mà không tốn lại chi phí phân tích video ở các tầng trước.
