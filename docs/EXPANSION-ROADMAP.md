# Định hướng Mở rộng Hệ thống (Expansion Roadmap)

Tài liệu này trình bày thiết kế kỹ thuật chi tiết cho các hướng mở rộng tiếp theo của hệ thống **AI KOC Discovery**, bao gồm:
1. **Kiến trúc REST API & Web Admin Dashboard (Dual-Interface)**
2. **Tầng S6 — Tự động hóa Liên hệ KOC & Khép vòng Chấm điểm 100/100 (Automated Outreach & Auto-Reselect Loop)**
3. **Đối chiếu Đa nguồn & Kiểm toán Bình luận qua TikTok API (Multi-Source Cross-Verification)**
4. **Mở rộng Quy mô lớn ($N=500+$ KOC), Tối ưu Chi phí & Autonomous Multi-Agent**

---

## Phần 1. Kiến trúc REST API & Admin Dashboard (Dual-Interface)

Trong phiên bản hiện tại, hệ thống đã tự động sinh báo cáo trực quan độc lập `reports/dashboard.html` sau mỗi lần chạy. Nhờ thiết kế tách biệt hoàn toàn giữa **Core Engine (`src/koc/`)**, tầng lưu trữ **SQLite WAL** và giao diện dòng lệnh (`cli.py`), hệ thống đã sẵn sàng để nâng cấp lên mô hình **REST API + Interactive Admin Panel** mà **không cần sửa lại logic lõi của các tầng `S0 → S5`**.

### 1.1. Vì sao kiến trúc hiện tại thuận lợi để gắn API + Dashboard?

Toàn bộ trạng thái của hệ thống không nằm trong RAM hay chỉ in ra màn hình console, mà đã được lưu trữ có cấu trúc trong **SQLite ở chế độ WAL (Write-Ahead Logging)** — cho phép worker chạy ngầm ghi dữ liệu đồng thời với các request HTTP đọc dữ liệu từ API mà không gây khóa bảng (non-blocking reads):

1. **Quản lý phiên chạy (`runs`):** Mỗi chiến dịch tìm kiếm KOC là một `run_id` độc lập, lưu đầy đủ `config_json`, `BriefAnalysis`, `status` và mốc thời gian.
2. **Theo dõi tiến độ thời gian thực (`tasks`):** Từng tầng (`S0` → `S5`) và từng thực thể (`creator_id`, `video_id`) đều cập nhật trạng thái `pending | running | done | failed | waiting_kalodata` vào DB. Giao diện Admin chỉ cần truy vấn bảng này để hiển thị thanh tiến độ (Progress Bar) và phễu chuyển đổi theo thời gian thực.
3. **Truy xuất bằng chứng đa phương thức (`evidence`, `videos`, `judgements`):** Đường dẫn các khung hình JPEG (`frames_json`), bản bóc băng tiếng Việt có timestamp (`transcript_path`) và điểm số từng tiêu chí đều được lưu dạng JSON chuẩn hóa → giao diện Web có thể mở ngăn chi tiết (drawer) hiển thị trực tiếp ảnh chụp màn hình video TikTok và tô sáng câu thoại ngay trên thẻ KOC.
4. **Kiểm toán chi phí & hiệu năng (`usage_ledger`):** Mọi lời gọi Kalodata, LLM và ASR đều được ghi nhận từng dòng kèm `credits`, `tokens_in`, `tokens_out`, `cost_usd`, `latency_ms` → Dashboard dễ dàng vẽ biểu đồ chi phí và tỷ lệ cache hit theo thời gian thực.

---

### 1.2. Mô hình Kiến trúc Dual-Interface (`CLI + FastAPI + Web Dashboard`)

Giữ nguyên **Core Engine** độc lập; **CLI (`typer`)** và **FastAPI (`api.py`)** đóng vai trò là hai lớp giao tiếp mỏng (thin wrappers) cùng gọi vào Core Engine và đọc/ghi chung cơ sở dữ liệu SQLite:

```
                 ┌───────────────────────────────────────┐
                 │        Web Admin Panel / Dashboard    │ (HTML/JS hoặc React)
                 └───────────────────┬───────────────────┘
                                     │ REST API / SSE
         ┌───────────────┐   ┌───────▼───────────┐
         │ CLI           │   │ FastAPI           │ (~150 dòng code)
         │ (src/koc/cli) │   │ (src/koc/api.py)  │
         └───────┬───────┘   └───────┬───────────┘
                 │                   │
                 ▼                   ▼
┌─────────────────────────────────────────────────────────┐
│               KOC Discovery Core Engine                 │
│     (stages S0 -> S5, scoring, select, evidence, llm)   │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│  SQLite (WAL Mode) + Disk (runs/<id>/media,frames,asr)  │
└─────────────────────────────────────────────────────────┘
```

---

### 1.3. Thiết kế Hệ thống API Endpoints

| Method & Endpoint | Chức năng trên Admin Dashboard | Nguồn dữ liệu / Xử lý |
|---|---|---|
| `POST /api/runs` | Nhập Brief tự nhiên + cấu hình (ngân sách, quy mô ứng viên), khởi chạy chiến dịch ngầm qua worker. | Khởi tạo bản ghi `runs` + gọi `run_pipeline(ctx)` |
| `POST /api/runs/{id}/pause` | Nút **"Pause / Stop"** chủ động để tạm dừng phiên chạy một cách an toàn ở ranh giới tác vụ. | Bật cờ `cancel_event` của `run_id` |
| `POST /api/runs/{id}/resume` | Nút **"Resume"** để chạy tiếp phiên bị tạm dừng hoặc gián đoạn (tận dụng 100% cache đã lưu). | Gọi `reset_stale_running` + `reset_retryable_failed` + chạy tiếp |
| `GET /api/runs` | Danh sách lịch sử các chiến dịch đã chạy, trạng thái, tổng credit và chi phí AI. | Truy vấn bảng `runs` + tổng hợp `usage_ledger` |
| `GET /api/runs/{id}/status` | Xem tiến độ trực tiếp (Live Progress): đang ở tầng nào (`S0–S5`), số lượng task `done/running/failed`, số ứng viên còn lại sau mỗi tầng phễu. | `SELECT stage, status, COUNT(*) FROM tasks GROUP BY stage, status` |
| `GET /api/runs/{id}/results` | Xem **Top 5 KOC chính thức + 2 Dự phòng**, bảng điểm (`Đã đo X/65`), lý do đề xuất, biểu đồ độ nhạy ngân sách và danh sách KOC bị loại (`excluded`). | Kết quả tầng `S5` + `dashboard.collect(ctx)` |
| `GET /api/runs/{id}/kocs/{creator_id}` | **Drawer chi tiết 1 KOC:** xem trực tiếp 6 khung hình đã trích xuất từ video, đọc toàn bộ transcript có timestamp và danh sách bằng chứng (`evidence_id`). | Bảng `evidence`, `videos` + phục vụ file tĩnh từ `runs/<id>/frames/` |
| `GET /api/runs/{id}/benchmark` | Xem bảng thống kê Token, Kalodata Credits, Latency, Cache Hit theo từng tầng (`S0–S5`) và ngoại suy chi phí ở quy mô $N=500$. | `Ledger` rollup + `audit_numeric_claims()` |
| `POST /api/runs/{id}/reselect` | Nhập **báo giá thực tế** và **điểm khán giả xác minh từ ảnh Analytics** của KOC để tính lại tổ hợp 5 KOC tối ưu tức thì (0 credit). | Cập nhật dữ liệu `human-verified` + chạy lại tầng `S5` |

---

### 1.4. Các điểm kỹ thuật kết nối Core Engine với API

1. **Dừng chủ động từ giao diện (Graceful Pause / Cancel):**
   - Bổ sung `cancel_event: threading.Event | None = None` vào `StageRunner.run()`. Trước khi worker bắt đầu một task mới, kiểm tra `if cancel_event and cancel_event.is_set(): return`.
   - Cho phép người dùng bấm **Pause** ngay trên giao diện Web ở giữa tầng S2/S4 rồi bấm **Resume** để kiểm chứng trực quan cơ chế phục hồi không mất phí.
2. **Phục vụ trực tiếp khung hình video (Static Media Mount):**
   - Trong bảng `videos`, cột `frames_json` đã lưu sẵn đường dẫn tương đối (`runs/<run_id>/frames/<video_id>/frame_00_t0.5.jpg`). FastAPI chỉ cần mount thư mục `frames` qua `StaticFiles` là người duyệt có thể xem trực tiếp các khung hình hook 3s đầu và cảnh demo sản phẩm ngay trên trình duyệt.

---

## Phần 2. Tầng S6 — Tự động hóa Liên hệ KOC & Khép vòng Chấm điểm 100/100 (Automated Outreach & Auto-Reselect Loop)

### 2.1. Bài toán sản phẩm: Khép kín khoảng trống 35/100 điểm chưa đo được

Ở cuối tầng S5 hiện tại, hệ thống chấm **tối đa 65/100 điểm** từ dữ liệu đo được (Hiệu suất 25đ + Nội dung 25đ + Hình ảnh/Video 15đ) và tách riêng **35/100 điểm chưa có dữ liệu** (Khán giả 25đ + Hợp tác/Báo giá thật 10đ) thành danh sách việc cần xác minh.

Đồng thời, kết quả của tầng S2b và S5 **đã chuẩn bị sẵn 3 đầu vào có cấu trúc**:
- **Thông tin liên hệ (`contacts` từ S2b):** `email`, `zalo`, `tiktok` của từng KOC.
- **Danh sách câu hỏi xác minh riêng theo từng KOC (`verify_before_contract` từ S5):** Được cá nhân hóa dựa trên các cờ rủi ro đã phát hiện (ví dụ: xác minh xung đột độc quyền với đối thủ Anessa/Maybelline, yêu cầu bỏ claim tuyệt đối về an toàn cho trẻ 6 tháng tuổi, xin ảnh chụp Analytics Nữ 18–30).
- **Giá trần đàm phán (`price_ceiling_vnd`) & 2 KOC Dự phòng (`backups` từ S5):** Quy tắc hành động rõ ràng khi báo giá thực tế vượt ngân sách.

Việc bổ sung **Tầng S6 (Automated Outreach & Negotiation Loop)** giúp tự động hóa quá trình liên hệ KOC, thu thập nốt 35/100 điểm còn thiếu và tự động điều chỉnh danh sách lựa chọn khi báo giá thực tế thay đổi.

---

### 2.2. Luồng Kiến trúc Tầng S6 (4 Bước Khép kín)

```
[Đầu ra S5: 5 KOC chính thức + 2 Dự phòng + contacts + verify_before_contract + price_ceiling_vnd]
       │
       ▼
[S6.1] Evidence-Grounded Outreach Generator (LLM role=reason)
       → Sinh bản nháp Email / Zalo cá nhân hóa cho từng KOC (trích đúng video/điểm mạnh từ kho evidence)
       │
       ▼
[S6.2] Human-in-the-Loop Approval Gate & Multi-Channel Dispatcher
       → Bảng `outreach_tasks` (drafted → approved → sent → replied | timeout_48h)
       → Gửi qua Email (SMTP/Gmail API), TikTok Creator Marketplace Invite hoặc Zalo OA/ZNS
       │
       ▼
[S6.3] Multimodal Inbox Parser (LLM role=video / Vision OCR)
       → Đọc email/tin nhắn phản hồi + OCR ảnh chụp màn hình TikTok Analytics do KOC gửi
       → Trích xuất: Báo giá thật (VNĐ), % Nữ, % 18–30 tuổi, % Việt Nam, xác nhận điều khoản
       → Chấm tự động 25đ Khán giả + 10đ Hợp tác (gắn nhãn provenance: `human-verified`)
       │
       ▼
[S6.4] Auto-Fallback & Combinatorial Reselect (`koc reselect`, 0 credit)
       ├─ Nếu Báo giá thật ≤ Giá trần & Khán giả khớp → Chốt hợp đồng (Điểm hoàn chỉnh Y/100)
       └─ Nếu Báo giá thật > Giá trần HOẶC KOC từ chối / quá 48h không phản hồi:
          → Chạy lại thuật toán duyệt tổ hợp S5 với giá thật (0 credit, vài mili-giây)
          → Tự động đôn KOC [DỰ PHÒNG] lên thay thế & kích hoạt gửi lời mời cho KOC dự phòng
```

---

### 2.3. Các nguyên tắc kỹ thuật & an toàn trong Tầng S6

1. **Cá nhân hóa dựa trên bằng chứng (Chống Spam):**
   - Tin nhắn liên hệ không dùng mẫu chung chung mà trích dẫn trực tiếp video tiêu biểu của KOC đó từ bảng `evidence` (ví dụ: đề cập đúng chủ đề video hoặc phong cách review thực tế của kênh), tăng tỷ lệ phản hồi của KOC.
2. **Cổng duyệt của con người & Giới hạn tần suất gửi (Anti-Ban & Brand Safety Guard):**
   - Không cho phép hệ thống tự động nhắn tin hàng loạt qua tài khoản Zalo cá nhân hoặc tự ý cam kết ngân sách khi chưa có xác nhận.
   - Mọi bản nháp liên hệ đều đi qua trạng thái `drafted → approved_by_marketer` trên Dashboard trước khi gửi, kèm bộ điều tiết tốc độ gửi (rate-limiting) theo kênh chính thống.
3. **Tách biệt rõ nguồn gốc dữ liệu (`Provenance Tracking`):**
   - Khi hệ thống chấm bổ sung 25 điểm Khán giả từ ảnh chụp TikTok Analytics và cập nhật báo giá thật, các trường này được lưu vào bảng `evidence` với `kind = "analytics_verified"` và `kind = "quote_verified"`, hiển thị tách biệt với `65 điểm hệ thống tự đo` để người quản lý luôn kiểm chứng ngược được về file ảnh gốc do KOC cung cấp.

---

## Phần 3. Đối chiếu Đa nguồn & Kiểm toán Bình luận qua TikTok API (Multi-Source Cross-Verification)

### 3.1. Ba "điểm mù" của dữ liệu đơn nguồn Kalodata và giải pháp bổ sung

Việc chỉ dựa vào dữ liệu từ một công cụ phân tích thương mại điện tử như Kalodata sẽ gặp 3 giới hạn thực tế (đã được ghi nhận trong quá trình kiểm thử):

| Điểm mù trên Kalodata | Công cụ / API bổ sung | Giá trị mang lại cho bộ chấm điểm |
|---|---|---|
| **1. Thiếu nhân khẩu học khán giả (25/100 điểm)** (`% Nữ`, `% 18–30 tuổi`, `% Việt Nam`) | **TikTok Creator Marketplace (TTCM) Official API** / **TikTok Shop Partner (TSP) API** | Lấy trực tiếp dữ liệu nhân khẩu học chính chủ (First-party Audience Demographics) đối với các KOC liên kết Marketplace → tự động chấm **25/100 điểm Khán giả** (`ttcm-verified`) ngay trong pipeline mà không phải chờ KOC gửi ảnh chụp màn hình thủ công. |
| **2. Thiên lệch video thương mại & sai số lượt xem ước tính** (`video/rank` ưu tiên bài gắn giỏ hàng; một số video có `like > view` ước tính gây `er_anomaly`) | **TikTok Public Profile / Display API** | Lấy 10–15 bài đăng gần nhất trên tường kênh (gồm cả **video organic không gắn giỏ hàng**) để:<br>- Đối chiếu chéo `views/likes` thực tế với số ước tính của Kalodata.<br>- Đánh giá chính xác năng lực chia sẻ kiến thức skincare tự nhiên và tỷ lệ bão hòa quảng cáo (`ad_ratio`) thực chất. |
| **3. Chỉ có số lượng `comment_count`, không có nội dung bình luận** (không phân biệt được tương tác mua hàng thật với bot seeding hoặc tranh cãi tiêu cực) | **TikTok Comment Endpoint + LLM nhỏ (Comment Audit)** | Lấy **Top 50 bình luận** dưới 2 video đại diện của KOC đưa qua LLM nhỏ (`role=screen`, ~500 tokens/KOC) để đo:<br>- **Buying Intent Ratio:** Tỷ lệ bình luận hỏi giá, hỏi tình trạng da thật (*"da dầu mụn dùng có bí không?"*).<br>- **Community Red Flags:** Phát hiện dấu hiệu bot seeding lặp mẫu hoặc khán giả phản ánh hàng giả / kích ứng da. |

---

### 3.2. Vị trí đặt trong Phễu để bảo toàn hiệu quả chi phí (Stage S3.5 — Top-K Only)

**Nguyên tắc kiến trúc:** Tuyệt đối **không** gọi các API bên ngoài ở tầng S1/S2 cho toàn bộ 500 ứng viên. Tầng đối chiếu đa nguồn chỉ được kích hoạt tại **Tầng S3.5 (ngay sau khi S3 đã lọc còn Top-K = 7–15 KOC tiềm năng nhất)**:

```
S1–S3 (Kalodata + LLM nhỏ): Sàng lọc 500 ứng viên ──► giữ lại 15 KOC tiềm năng nhất
                                                            │
                                                            ▼
                            [Tầng S3.5: Multi-Source Cross-Verification (chỉ chạy cho 15 KOC)]
                            ├─ 1. TTCM / TSP API     → Lấy Audience Demographics chính chủ (25đ Khán giả)
                            ├─ 2. TikTok Feed API    → Lấy video organic + kiểm tra chéo view/ER thật
                            └─ 3. Comment Audit LLM  → Phân tích Top 50 bình luận/KOC (Buying Intent & Seeding)
                                                            │
                                                            ▼
                            [Tầng S4–S5: Phân tích Video đa phương thức & Duyệt tổ hợp trên hồ sơ đã làm giàu]
```

- **Tác động chi phí:** Vì chỉ chạy trên 15 KOC cuối cùng, bước kiểm toán bình luận bằng LLM nhỏ chỉ tiêu tốn khoảng `15 × 600 ≈ 9.000 tokens` (**< $0.01 / chiến dịch**), giữ nguyên lợi thế tiết kiệm ~95% chi phí của kiến trúc phễu nhưng nâng cao đáng kể độ tin cậy trước khi ra quyết định.

---

## Phần 4. Mở rộng Quy mô lớn ($N=500+$ KOC), Tối ưu Chi phí & Autonomous Multi-Agent

1. **Mở rộng quy mô lên 500–2.000 KOC:**
   - Toàn bộ độ rộng phễu trong `config/defaults.yaml` đã được tham số hóa (`funnel.candidates: 500`, `after_2a: 100`, `after_3: 25`).
   - Khi số ứng viên vào vòng cuối $K > 50$, bộ chọn tổ hợp ở `src/koc/select.py` có thể chuyển từ duyệt vét cạn $\binom{K}{5}$ sang bộ giải quy hoạch tuyến tính nguyên (ILP / Branch-and-Bound) với cùng hàm mục tiêu và các ràng buộc cứng.
   - Chuyển đổi tầng lưu trữ từ SQLite sang **PostgreSQL** kết hợp hàng đợi tác vụ phân tán khi cần chạy nhiều worker process trên nhiều máy chủ.
2. **Tối ưu thêm 50–70% chi phí AI ở môi trường Production:**
   - **Batch API (−50% chi phí):** Các tác vụ chấm điểm hàng loạt ở tầng S3 và phân tích video ở tầng S4 không đòi hỏi phản hồi tức thì dưới 1 giây, rất phù hợp để gửi qua Batch API của Anthropic / Gemini nhằm giảm một nửa đơn giá token.
   - **Native Prompt Caching:** Bổ sung adapter gọi trực tiếp SDK của provider kèm cờ `cache_control` tường minh cho phần rubric cố định ở đầu system prompt.
3. **Kiến trúc Autonomous Agent 2 tầng & Nền tảng Điều phối (Supervisor + Per-KOC Investigator / Agent SDK / LangGraph / Temporal):**
   - Trong bản hiện tại, hàng đợi `tasks` SQLite + `Governor` + `Bounded Planner` đã đủ gọn nhẹ, tất định và chịu lỗi tốt cho 1 tiến trình đơn. Khi chuyển sang quy mô phân tán đa máy chủ hoặc tác vụ điều tra dài ngày:
     - **Supervisor & Workflow Orchestrator (LangGraph / Temporal):** Tự động quay lại tầng S1 mở rộng thêm lát cắt tìm kiếm nếu thiếu ứng viên hoặc điều phối hàng nghìn chiến dịch song song với durable execution.
     - **Per-KOC Investigator Sub-agent (Agent SDK):** Với riêng top 7–15 KOC ở vòng cuối có cờ nghi vấn (như `er_unusually_high` hoặc nghi ngờ tương tác ảo), khởi chạy một sub-agent có ngữ cảnh cô lập (isolated context window) để gọi thêm các endpoint chuyên sâu (`comment/insight`, `product/detail`) mà không làm phình ngữ cảnh chung của toàn pipeline.
4. **Vòng phản hồi sau chiến dịch (Post-Campaign Feedback Loop):**
   - Sau khi chiến dịch kết thúc, nhập dữ liệu hiệu quả thực tế (CPC, CPA, GMV thực đạt được của 5 KOC đã thuê) ngược lại hệ thống để hiệu chỉnh trọng số bộ tiêu chí (`scoring.weights`) theo từng ngành hàng.
