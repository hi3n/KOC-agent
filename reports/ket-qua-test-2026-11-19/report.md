# Báo cáo đề xuất KOC — kem chống nắng

`run_id=demo_sunscreen` · as_of=2026-11-18 · date_range=2026-10-20~2026-11-18 · seed=42

Models (cấu hình được, không fix cứng): `{"brief": "ag/claude-sonnet-5-5", "screen": "ag/claude-sonnet-5-5", "video": "ag/claude-opus-5-5", "reason": "ag/claude-sonnet-5-5"}`


## 1. Brief và phân tích của AI (S0)

> Một thương hiệu mỹ phẩm Việt Nam muốn tìm 5 KOC TikTok phù hợp để quảng bá sản phẩm kem chống nắng.
Khách hàng mục tiêu: Nữ, 18–30 tuổi.
Ngân sách chiến dịch: 30 triệu VNĐ.
Đánh giá dựa trên dữ liệu hiệu suất, nội dung và hình ảnh/video.
Kết quả cần có lý do đề xuất và bằng chứng cụ thể.

- Sản phẩm: **Kem chống nắng (mỹ phẩm Việt Nam)**; mục tiêu: **conversion**; khán giả: female 18-30 (VN)
- Danh mục Kalodata: [('601602', 'Kem chống nắng cho da mặt')]
- Từ khóa ngách: kem chống nắng, chống nắng, sunscreen, spf, spf50, skincare, chăm sóc da, review kem chống nắng, nâng tone, kiềm dầu, da dầu, routine
- Đối thủ (AI đề xuất — **giả định, cần thương hiệu xác nhận**): Anessa, La Roche-Posay, Skin Aqua, Bioré, Neutrogena, Cetaphil, Sunplay, Innisfree, Cocoon, Skin1004
- Ngân sách: 30,000,000 VNĐ
- AI hiểu brief: Brief tìm 5 KOC TikTok cho kem chống nắng, nữ 18-30, VN, ngân sách 30 triệu VNĐ (~6 triệu/KOC). Brief không nêu rõ mục tiêu nên mặc định conversion vì dữ liệu Kalodata thiên thương mại. Chọn danh mục lá 'Kem chống nắng cho da mặt', khớp trực tiếp sản phẩm. Đối thủ là giả định: brief không nêu, đây là thương hiệu chống nắng phổ biến ở VN. Tuổi/giới tính khán giả lấy từ brief, không suy đoán từ nội dung creator.

## 2. Phễu

| Tầng | Vào | Ra | Ghi chú |
|---|---|---|---|
| S1 rank đa lát cắt | — | 30 | dedupe round-robin, INDEPENDENT |
| S2a video stats + code | 30 | 12 | loại cứng + cắt |
| S2b detail | — | 12 | bio, contacts, follower spike |
| S3 text LLM | 12 | 7 | batch 10/call |
| S4 video LLM | 7 | 14 video | 2 video đại diện/creator |
| S5 chọn tổ hợp | 7 | 5 + 2 dự phòng | code, ràng buộc cứng |

## 3. Đề xuất

*Lưu ý chất lượng đọc đúng: điểm hiệu suất đo trên TOÀN bộ video lấy được (tối đa 100), nhưng phân tích nội dung AI chỉ trên 2 video đại diện/creator. Nếu video mẫu lạc ngách chống nắng, lý do sẽ nói thẳng và checklist yêu cầu xem thêm video đúng ngách trước khi chốt — hệ thống không giấu khoảng trống bằng chứng. Ngách fit hiện là trọng số mềm, chưa gate cứng (hướng mở rộng: tăng trọng số semantic fit + thêm credit cho video analysis).*


### Công chúa cam thường (@vanhmakeupcute) — Chủ lực. Số liệu bán hàng đo được mạnh nhất nhóm kênh này, nhưng kênh nguội nên cần theo dõi sát.

**Điểm đã đo: 35.28/65.0** (hiệu suất 9.56/25 · nội dung 17.0/25 [phần đo 25.0/25] · hình ảnh 8.72/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `cold_channel` view/follower 0.015 thấp — kênh nguội hoặc follower ảo; `competitor_recent` nhắc đối thủ: Anessa, Cocoon, Neutrogena; `knowledge_issue` Không nêu chỉ số SPF/PA, lượng dùng hay việc thoa lại; video chỉ có kể trải nghiệm và giới thiệu sản phẩm.; Câu về công nghệ nano bị transcript làm méo ('giúp giảm tới 10% áp được lê làn ra'), không rõ giảm 10% chỉ số gì nên không kiểm chứng được.; K; `exaggerated_claims` hoàn toàn không gây bết dính chăng lố hay là bí bách gì luôn; an toàn cho da nhạy cảm, da mụn, thậm chí là brain có thông tin là da em bé từ 6 tháng tuổi cũng dùng được; khả năng chống nước và chống bụi mịn thì an toàn luôn đỉnh từ trước đến nay rồi;; `knowledge_issue` Video review cushion trang điểm, không nói về chống nắng (SPF/PA, thoa lại, lượng dùng); chấm trung tính 0.5.; `exaggerated_claims` đảm bảo là ai làm theo cũng sẽ thành công; Mọi người có thấy là mồ hôi chảy ra ướt tóc mà lớp nền nó vẫn bám trên da; Mình đang dùng cái màu 1.5 thì thấy tiệp ra cực kỳ tự nhiên; đặc biệt là bên màu sốt cả ngày dài thì em này xứng đáng bỏ vào giỏ hàn; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Có tín hiệu bán hàng đo được (GPM, doanh thu shop) và đã có video demo da chỉ thoa kem chống nắng. Rủi ro: view/follower thấp, nhắc đối thủ, claim phóng đại về an toàn. Chỉ xem 2/43 video nên kết luận còn mỏng.

- video_gpm 558148.92, doanh thu shop 95421697.39. Số đo được, liên quan trực tiếp mục tiêu conversion.  
  ↳ bằng chứng: `ev_564adbe64d4f`
- Theo transcript có cảnh 'da mình chỉ có kem chống nắng' (70.5-72.4s) rồi đánh lớp nền lên (72.4-78.1s). Chưa xác minh bằng hình.  
  ↳ bằng chứng: `ev_1b2a862b7ddf, ev_3ae9cb6dbe8d`
- Mẫu 43 video: đăng 10.03 bài/tuần, ad_ratio 0.256. Kênh hoạt động đều, không bão hòa quảng cáo.  
  ↳ bằng chứng: `ev_f4b1fb258777`
- Một video chấm hook_strength 0.7, demo_quality 0.6 (AI chấm, confidence 0.45). Chỉ là tham khảo.  
  ↳ bằng chứng: `ev_63350c0d78fe`
- Đã xem **2/43** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: view_follower_ratio 0.015 (cờ kênh nguội). median_views 3153 so với mean_views 32326.5: phân phối lệch, vài video kéo trung bình.; Nhắc đối thủ Anessa, Cocoon, Neutrogena. Tiêu đề có #HoptaccungAnessa, caption có #hoptaccungmaybelline. Cần kiểm tra ràng buộc hợp tác với đối thủ.; Claim tuyệt đối 'an toàn cho da nhạy cảm... da em bé từ 6 tháng tuổi' (ev_d11ca4169153) và 'chống nước, chống bụi mịn an toàn luôn' (ev_74eda293ce7a) không có dẫn chứng. Không nêu SPF/PA, lượng dùng, thoa lại. Cờ ad_no_disclosure cho người duyệt.
- Giá giả định: 7,000,000 VNĐ · giá trần: **7,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả: tỷ lệ nữ 18-30, VN. Chưa đo được.; Báo giá thật so với giá trần 7,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Hỏi có hợp đồng/độc quyền đang chạy với Anessa hoặc Maybelline không.; Yêu cầu kịch bản bỏ claim tuyệt đối về an toàn; gắn nhãn quảng cáo rõ.; Hỏi nguyên nhân view/follower thấp (kênh nguội hay follower ảo).
- Liên hệ: email=[redacted], tiktok=vanhmakeupcute, zalo=[redacted]

### Phương Sena (@phuongsena) — Chủ lực. Kênh bán hàng quy mô lớn, median views cao hơn kênh anchor còn lại trong bộ, nhưng nội dung mẫu lệch ngành.

**Điểm đã đo: 39.43/65.0** (hiệu suất 11.91/25 · nội dung 21.9/25 [phần đo 25.0/25] · hình ảnh 5.62/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `knowledge_issue` Video không nói về chống nắng. knowledge_accuracy để trung tính 0.5.; Cờ skincare (ngoài rubric chống nắng): 'kích thước phân tử nhỏ bằng tế bào' là so sánh mơ hồ, không có cơ sở rõ.; Cờ skincare: số liệu thành phần không khớp. Tổng hoạt chất nói 77%; `exaggerated_claims` khả năng hấp thụ của nó so với những cái dọc này nó là gấp 300%; Nên đế là lý do tại sao nó cực hiệu quả luôn vì nó cực mạnh các chị ạ; 30% thành phần vitamin C L-ascorbic Acid tinh khiết vào cao cấm nhất trên thế giới của Anh Quốc; Thứ 2, siêu căng ; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý; `knowledge_issue` Video nói về tẩy trang, không về chống nắng; chỉ nhắc thành phần 'dùng trong kem chống nắng hàng đầu' như mồi quảng cáo, không có kiến thức SPF/PA/thoa lại.; 'không cần dựa (rửa) mặt cũng được luôn' sau tẩy trang: lời khuyên bỏ bước rửa mặt cần người; `exaggerated_claims` Thành phần tẩy trang chống lão hóa x, ... siêu cao cấp và chỉ dùng trong những dòng kem chống nắng hàng đầu của thế giới.; Mà cứ 1, 2 triệu, 1 hút ấy.; tẩy xong không khô, không giác, không cần dựa mặt cũng được luôn.; không kim loại nặng, không huỳn; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Có lịch sử bán hàng lớn và phong cách chốt đơn kiểu livestream, hợp mục tiêu conversion. Hai video xem được đều không về chống nắng và có claim thiếu căn cứ. Cần brief chặt và duyệt kịch bản.

- Doanh thu shop 1579381679.89, new_follower_ratio 0.0332. Số đo được. Mẫu video_gpm 25522.85.  
  ↳ bằng chứng: `ev_306cb9dcfab1`
- Mẫu 65 video: median_views 6996, đăng 15.17 bài/tuần, stability 0.535.  
  ↳ bằng chứng: `ev_9c76d173fcc2`
- Một video là đoạn cắt livestream bán hàng, nói kiểu tư vấn chốt đơn. Phong cách gần mục tiêu conversion (theo transcript).  
  ↳ bằng chứng: `ev_fc587af2cb0e`
- Đã xem **2/65** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Cả 2 video xem đều không về chống nắng; demo_quality 0.2. Chưa có bằng chứng về nội dung chống nắng.; Claim thiếu căn cứ: 'hấp thụ gấp 300%' (ev_52281be14e81); tổng hoạt chất nói 77% nhưng 30%+12%+33% = 75% (ev_79a891631325); 'không có chất hoạt động bề mặt' ở sản phẩm tẩy trang đáng ngờ (ev_4f0d0884d672). Lời khuyên bỏ bước rửa mặt cần duyệt.; ad_ratio 0.323, cờ ad_no_disclosure. Hai số doanh thu trong kho lệch nhau (1579381679.89 và total_revenue 72923449.64), chưa rõ cách tính. Chỉ xem 2/65 video.
- Giá giả định: 7,000,000 VNĐ · giá trần: **7,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả: nữ 18-30, VN.; Báo giá thật so với giá trần 7,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Hỏi nguồn và cách tính doanh thu; đối chiếu hai con số lệch nhau.; Duyệt kịch bản trước đăng; cấm claim số liệu không nguồn.; Xem thêm video thuộc nhóm chống nắng/trang điểm nếu có.
- Liên hệ: tiktok=phuongsena

### Chang Chăm Chỉ (@changaffiliate) — Tầm trung. Hiệu suất và quy mô bán hàng cao nhất bộ, nhưng ad_ratio 0.99 làm giảm độ tin cậy.

**Điểm đã đo: 33.52/65.0** (hiệu suất 18.09/25 · nội dung 7.46/25 [phần đo 25.0/25] · hình ảnh 7.97/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `ad_saturated` tỷ lệ video quảng cáo 0.99 — uy tín thấp; `knowledge_issue` Video về kem nền thỏi, không nói về chống nắng (SPF/PA, thoa lại, lượng dùng); chấm trung tính 0.5.; Thông tin thương hiệu cần duyệt: creator nói hãng 'rất nổi tiếng bên Hàn', trong khi Obagi thường được biết là thương hiệu Mỹ.; `exaggerated_claims` Nói chung là đỉnh á; rất là tự nhiên... như da thật luôn; vẫn che được những cái nốt mụn thâm này; Con này nâng tông rất đẹp luôn; Bà nào thấy giá hời lụm sớm nhé (gây khẩn cấp, so sánh giá hơn 800k và gần 400k chưa kiểm chứng); `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý; `knowledge_issue` Video không nói về chống nắng (sáp tẩy tế bào chết/mụn đầu đen); chấm trung tính 0.5.; Ngoài phạm vi chống nắng, cần người duyệt kiểm tra: video cho rằng hạt vón ra khi chà là tế bào chết/bụi bẩn ('những hạt tảy ra chết'). Với sản phẩm dạng gel/sáp t; `exaggerated_claims` làm sạch sâu thông tháng lỗ cho lông hút sạch những bự bẩn; Chối lần đầu tiên thôi mọi người sờ vào phần mũi Mọi người cảm thấy nó miễn tức thi luôn; nó sẽ hỗ trợ thu hẹp lỗ cho lông rất là tốt; Mọi người sợ sạch cho mọi người làm sáng vùng mũi hơn; ; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Kênh tầm trung có reach lớn so với số follower và GPM cao, thiên về chốt giá và kênh mua. Gần như toàn video quảng cáo nên cần kiểm soát cách lồng ghép. Chưa có video chống nắng trong mẫu xem.

- Mẫu 100 video: median_views 289953.0, view_follower_ratio 3.3913, stability 0.587. Reach vượt xa số follower 85500.  
  ↳ bằng chứng: `ev_0be6f3121801`
- video_gpm 381977.67, doanh thu shop 924150661.77, new_follower_ratio 0.083. Số đo được.  
  ↳ bằng chứng: `ev_8f71b2a358b7`
- Theo transcript, có thoa sáp lên mũi, massage 2-3 phút rồi lau/rửa. Có nêu kênh mua chính hãng trên sàn. Chưa xác minh bằng hình.  
  ↳ bằng chứng: `ev_249ec5c14f64, ev_084f181afda9`
- Video nêu giá trực tiếp (hơn 8 lít so với gần 4 lít) để chốt đơn. Phong cách thúc mua phù hợp conversion, nhưng so sánh giá chưa kiểm chứng.  
  ↳ bằng chứng: `ev_ed6a30dba9e9`
- Đã xem **2/100** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: ad_ratio 0.99 (cờ bão hòa quảng cáo). Khán giả có thể đã quen nội dung bán hàng. Cờ ad_no_disclosure ở cả 2 video xem.; Không video nào về chống nắng (kem nền thỏi, sáp tẩy mụn đầu đen). Nói hãng Obagi 'nổi tiếng bên Hàn', cần duyệt thông tin thương hiệu (ev_bb848d2f26f2). Claim 'thu hẹp lỗ chân lông', 'làm sạch sâu' không có căn cứ.; Chỉ xem 2/100 video. ER trung vị 0.00536 thấp.
- Giá giả định: 6,000,000 VNĐ · giá trần: **6,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả: nữ 18-30, VN.; Báo giá thật so với giá trần 6,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Cách gắn nhãn quảng cáo trong video; cam kết disclosure.; Xem thêm video review chống nắng/skincare trước khi chốt brief.; Thái độ hợp tác với tần suất đăng 23.33 bài/tuần: có nhận brief riêng không.
- Liên hệ: tiktok=changaffiliate

### Cẩm Linh (@calinle) — Tầm trung nhỏ, thử nghiệm. Kênh ít bão hòa quảng cáo nhưng chưa có bằng chứng ngành làm đẹp hay chống nắng.

**Điểm đã đo: 32.93/65.0** (hiệu suất 13.38/25 · nội dung 13.46/25 [phần đo 25.0/25] · hình ảnh 6.09/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `knowledge_issue` Video không nói về chống nắng/skincare; đây là try-on váy dự tiệc. Điểm kiến thức để trung tính 0.5.; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý; `knowledge_issue` Video không nói về chống nắng/skincare; nội dung là nước xả vải Downy Luxe, ngoài ngành nên chấm trung tính 0.5.; `exaggerated_claims` Hương thơm được phát triển từ các nhà điều hương hàng đầu mà sắc thái tương tự như các gióng Edity; mang lại cảm giác hương thơm đậm không hề kém cạnh mấy trai nước khoa nổi tiếng luôn nha; hương được ướp sâu và từng sởi vãi, giúp lưu hương xuất ngày

Kênh nhỏ, ad_ratio thấp, median views ổn so với 49700 follower. Hai video xem là try-on váy và nước xả vải, không liên quan skincare. Số liệu bán hàng thấp nên chỉ nên là vị trí thử nghiệm.

- Mẫu 26 video: median_views 5819.5, ad_ratio 0.115, đăng 6.07 bài/tuần. Kênh ít bão hòa quảng cáo.  
  ↳ bằng chứng: `ev_44931eb1aaca`
- Video nước xả vải có ad_disclosure_ok true: gắn nhãn quảng cáo rõ ở 1 video đã xem.  
  ↳ bằng chứng: `ev_39ab8a3466f8`
- Hook một video chấm 0.6, audio_clarity 0.6 (AI chấm, confidence 0.35). Chỉ tham khảo.  
  ↳ bằng chứng: `ev_eef530cd0cb8`
- Đã xem **2/26** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Không có nội dung skincare hay chống nắng trong mẫu; demo_quality 0.1 ở cả 2 video. Chưa có bằng chứng bán hàng làm đẹp.; video_gpm 0.0, doanh thu shop 3275081.24: tín hiệu conversion yếu.; Có claim phóng đại ở video nước xả vải ('hương thơm không kém nước hoa nổi tiếng'). Cờ ad_no_disclosure ở video try-on. Chỉ xem 2/26 video.
- Giá giả định: 5,000,000 VNĐ · giá trần: **5,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả: nữ 18-30, VN.; Báo giá thật so với giá trần 5,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Xin thêm video skincare/làm đẹp trước đó nếu có.; Thái độ hợp tác; có sẵn sàng quay demo thoa kem lên da, texture, bệt trắng không.
- Liên hệ: email=[redacted], tiktok=calinle

### Khoa Alpha 💪 🇻🇳 (@khoaalpha99) — Tầm trung nhỏ, thử nghiệm. GPM đo được khá nhưng mẫu nội dung lệch ngành, độ tin cậy phân tích thấp.

**Điểm đã đo: 31.4/65.0** (hiệu suất 14.56/25 · nội dung 11.78/25 [phần đo 25.0/25] · hình ảnh 5.06/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `er_unusually_high` ER trung vị 0.49 cao bất thường — có thể kênh nhỏ/viral hoặc view ước tính thấp; kiểm tra mẫu video; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý; `knowledge_issue` Video chủ yếu nói về serum niacinamide 20%, không phải kem chống nắng. Chống nắng chỉ được nhắc lướt ('vẫn phải chống nắng'), không có SPF/PA, lượng dùng hay thoa lại.; Nhắc da 'bị cháy nắng cần dưỡng sáng lại' bằng serum nhưng không nêu biện pháp ch; `exaggerated_claims` ưu điểm đầu tiên của em nó là hỗ trợ kiềm dầu cực tốt; hầu như là nó sẽ khô ngay lập tức sau khi thoa; 100 ngày từ cha tài xế thành cha ơn wô; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Kênh nhỏ có video_gpm đáng chú ý và nhịp đăng ổn định. Nội dung là series đổi ngoại hình, serum niacinamide, chống nắng chỉ nhắc lướt. Dữ liệu video xem được yếu nên đây là vị trí thử nghiệm rủi ro cao.

- video_gpm 308586.78, new_follower_ratio 0.008. Số đo được; doanh thu shop 2517142.38 thấp.  
  ↳ bằng chứng: `ev_eca1f6c4eb5a`
- Mẫu 22 video: median_views 3974.0, stability 0.602, đăng 5.13 bài/tuần.  
  ↳ bằng chứng: `ev_53854d61880e`
- Video skincare có lời khuyên 'vẫn phải chống nắng, dưỡng ẩm' và nhắc test vùng da nhỏ. Có ý thức an toàn cơ bản, nhưng chống nắng chỉ nhắc lướt.  
  ↳ bằng chứng: `ev_3633e5eb183a, ev_7bfc469a3500`
- Đã xem **2/22** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: niche_fit 0.12, brand_risk 0.25; niche_keyword_ratio 0.091. Nội dung chủ yếu thay đổi ngoại hình, nhiều sản phẩm không liên quan.; ER trung vị 0.49021 cao bất thường (cờ). Transcript một video có thể là ảo giác ASR (confidence 0.15), không đánh giá được demo. ad_ratio 0.455, cờ ad_no_disclosure.; Không có SPF/PA, lượng dùng, thoa lại trong video xem. Transcript '200% acetyl glucosamine' cần nghe lại. Chỉ xem 2/22 video.
- Giá giả định: 5,000,000 VNĐ · giá trần: **5,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả: nữ 18-30, VN.; Báo giá thật so với giá trần 5,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Xem lại video gốc trực tiếp vì dữ liệu transcript/khung hình kém.; Kiểm tra ER bất thường và cách gắn nhãn quảng cáo.; Thái độ hợp tác; có chịu quay riêng nội dung chống nắng không.
- Liên hệ: tiktok=khoaalpha99

### [DỰ PHÒNG] Kiều Oanh Mê Làm Đẹp (@kieu_oanh_cosmetic) — Dự phòng. Thay vị trí tầm trung nếu một người rút. Có nội dung kem chống nắng duy nhất trong mẫu xem, nhưng kiến thức yếu.

**Điểm đã đo: 33.52/65.0** (hiệu suất 11.03/25 · nội dung 16.4/25 [phần đo 25.0/25] · hình ảnh 6.09/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `cold_channel` view/follower 0.019 thấp — kênh nguội hoặc follower ảo; `knowledge_issue` Ngụ ý 1 lớp mỏng buổi sáng là đủ bảo vệ ('sáng mọi người chỉ cần dặm cho em 1 lớp này thôi'). Không nói lượng dùng chuẩn, không nhắc thoa lại trong ngày.; Không nêu chỉ số SPF/PA, chỉ nói chung chung '6 màng lọc phổ rộng'.; Hiệu ứng nâng tông ('bật t; `exaggerated_claims` Lớp finish còn là đẹp hơn cả mọi người makeup luôn; kiềm dầu cực kì mạnh luôn; đẹp và lên da trắng hồng trắng sứ; kem trống nắng mà đẹp hơn cả Kewchon thì chỉ có xeo lắc mới làm được; mọi người đều có thể tham khảo trống nắng này cực kì tốt nha; dạc ; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý; `knowledge_issue` Không nói về chống nắng; chấm trung tính 0.5.; Skincare ngoài chống nắng (cần người duyệt): claim xịt khoáng/serum 'đi được đến tầng Hạ bì là tầng thứ 3' thiếu cơ sở; mỹ phẩm bôi ngoài da không được quảng cáo thấm tới hạ bì.; Claim 'lấp đầy lỗ chân l; `exaggerated_claims` Dưỡng chất này nó sẽ đi được đến tầng Hạ Bì là tầng thứ 3; Nó lấp đầy lỗ chân lông mà nó không cần tái tạo; nó dịu ngay lập tức sau khi mọi người xịt nha; Dưỡng chất nó đi nem nó vào từng cái lỗ chân lông, vì kích thước phân tử nó rất là nhỏ; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Kênh tầm trung 119000 follower, GPM đo được và ad_ratio 0.0. Là creator duy nhất trong danh sách có video nói trực tiếp về kem chống nắng. View thấp và kiến thức chống nắng có lỗ hổng.

- video_gpm 336493.24, doanh thu shop 813202301.55. Số đo được.  
  ↳ bằng chứng: `ev_7257c9aca60e`
- Có video nói trực tiếp về kem chống nắng ('một lớp kem chống nắng là sáng đủ ra ngoài'), thoa 2-3 lớp theo transcript; nhắc 6 màng lọc phổ rộng. Chưa xác minh bằng hình.  
  ↳ bằng chứng: `ev_12b0ab8a22d3, ev_e63ea8a98c0d`
- Mẫu 10 video: ad_ratio 0.0, stability 1.044.  
  ↳ bằng chứng: `ev_7c3ceafec190`
- Đã xem **2/10** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: median_views 2211.0, view_follower_ratio 0.0186 (cờ kênh nguội). Mẫu chỉ 10 video, kết luận yếu.; knowledge_accuracy 0.35: ngụ ý 1 lớp mỏng buổi sáng là đủ, không nêu SPF/PA, lượng dùng, thoa lại (ev_e777372fcc3a). Claim thấm 'tầng hạ bì' thiếu căn cứ (ev_889f67048d3e).; Metadata ghi không quảng cáo nhưng có kêu gọi inbox tư vấn (ev_7f85f2b64ca8); cờ ad_no_disclosure. Chỉ xem 2/10 video. Chưa có giá trần trong block.
- Giá giả định: 6,000,000 VNĐ · giá trần: áp trần của slot thay thế (dự phòng không nằm trong phân bổ ngân sách hiện tại)
- Xác minh trước chốt: Ảnh Analytics khán giả: nữ 18-30, VN.; Báo giá thật; block chưa có giá trần, giá giả định 6,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Duyệt kịch bản: bỏ claim 'một lớp là đủ', phải nêu lượng dùng và thoa lại.; Cách gắn nhãn khi bán/tư vấn qua inbox.; Thái độ hợp tác.
- Liên hệ: tiktok=kieu_oanh_cosmetic

### [DỰ PHÒNG] Mỏ hỗn là tao (@mykimmohon) — Dự phòng. Thay vị trí chủ lực nếu cần reach lớn, nhưng lệch ngành và bão hòa quảng cáo.

**Điểm đã đo: 32.1/65.0** (hiệu suất 18.38/25 · nội dung 6.6/25 [phần đo 25.0/25] · hình ảnh 7.12/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `ad_saturated` tỷ lệ video quảng cáo 0.91 — uy tín thấp; `knowledge_issue` Video không nói về chống nắng (sản phẩm là miếng dán mụn/hydrocolloid); chấm trung tính 0.5.; Cờ cho người duyệt (ngoài phạm vi chống nắng): câu 'Cái miếng dán mụn nhỏ là miếng nào cũng sẽ đều có thành phần này' không nêu thành phần cụ thể, mơ hồ, kh; `exaggerated_claims` Nó hút cái cục ngụng luôn, một lỗ xa quấy luôn; video không cáp nha; lá hết trơn nhân mụn luôn nè; Lá hết trơn luôn nè, cái miếng này dán hay thiệt; Lò này, lò này là cụ tổ của mấy cái miếng dán mụn luôn trời ơi; Gê chưa, kinh; `knowledge_issue` Video không nói về chống nắng/skincare; nội dung là tóc giả/mái giả che trán bò liếm, hói. Chấm trung tính 0.5.; Lạc ngành: không phù hợp đánh giá nội dung kem chống nắng.; `exaggerated_claims` nhìn kiểu nó khác hẳn luôn á; Cho nên bắt buộc là phải có cái mái để mà che lại.; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Reach rất lớn: median views cao so với 350900 follower. Nội dung xem được là miếng dán mụn và tóc giả, không liên quan chống nắng. ad_ratio 0.91 và tín hiệu bán hàng shop gần như bằng 0.

- Mẫu 100 video: median_views 268389.5, view_follower_ratio 0.7649, đăng 23.33 bài/tuần.  
  ↳ bằng chứng: `ev_8bec59221450`
- Theo transcript có demo gỡ miếng dán trên da, chỉ vào thứ lấy ra. Có kỹ năng demo cận cảnh, chưa xác minh bằng hình.  
  ↳ bằng chứng: `ev_744b695df104`
- new_follower_ratio 0.0325. Số đo được.  
  ↳ bằng chứng: `ev_89bd98b6461a`
- Đã xem **2/100** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: video_gpm 0.0, doanh thu shop 426499.66: tín hiệu conversion yếu so với reach. ad_ratio 0.91 (cờ bão hòa quảng cáo).; Lạc ngành: video xem là miếng dán mụn và tóc giả, demo_quality 0.1 ở video tóc giả (ev_bb6d789757ac). Không có nội dung chống nắng.; Claim phóng đại ('lấy hết trơn nhân mụn', ev_06649218a931). Cờ ad_no_disclosure. Chỉ xem 2/100 video. Chưa có giá trần trong block.
- Giá giả định: 7,000,000 VNĐ · giá trần: áp trần của slot thay thế (dự phòng không nằm trong phân bổ ngân sách hiện tại)
- Xác minh trước chốt: Ảnh Analytics khán giả: nữ 18-30, VN.; Báo giá thật; block chưa có giá trần, giá giả định 7,000,000 VNĐ.; Quyền dùng nội dung và Spark Ads.; Hỏi lý do doanh thu shop thấp dù reach lớn.; Cách gắn nhãn quảng cáo; xem thêm video skincare/chống nắng.; Thái độ hợp tác.
- Liên hệ: tiktok=mykimmohon

**Phương án thay thế** (chênh lệch điểm so với phương án 1):
- PA2: Phương Sena, Kiều Oanh Mê Làm Đẹp, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 · điểm 2.6277 (Δ -0.0271) · giá 29,000,000
- PA3: Mỏ hỗn là tao, Phương Sena, Kiều Oanh Mê Làm Đẹp, Cẩm Linh, Khoa Alpha 💪 🇻🇳 · điểm 2.6058 (Δ -0.0490) · giá 30,000,000

Hoán đổi 1 người (phương án 1): Công chúa cam thường → Kiều Oanh Mê Làm Đẹp (Δ điểm -0.0271); Phương Sena → Kiều Oanh Mê Làm Đẹp (Δ điểm -0.0909); Chang Chăm Chỉ → không có phương án tốt hơn; Cẩm Linh → không có phương án tốt hơn; Khoa Alpha 💪 🇻🇳 → không có phương án tốt hơn

## 4. Ngân sách (GIẢ ĐỊNH — không phải báo giá)

- Tổng giá giả định bộ 5: **30,000,000 VNĐ** / ngân sách 30,000,000
- **Hệ số giá tối đa còn khả thi: 1.0** (giá thật cao hơn mức này → vượt ngân sách, dùng phương án thay thế)
- Bảng giá theo tier là minh họa; chỉ tỷ lệ tương đối có ý nghĩa. Điểm chất lượng KHÔNG dùng giá.

| price_scale | khả thi | tổng giá (VNĐ) | bộ 5 tối ưu / ghi chú |
|---|---|---|---|
| 0.7x | ✓ | 21,000,000 | Công chúa cam thường, Phương Sena, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 |
| 0.85x | ✓ | 25,500,000 | Công chúa cam thường, Phương Sena, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 |
| 1.0x | ✓ | 30,000,000 | Công chúa cam thường, Phương Sena, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 |
| 1.03x | ✓ | 29,870,000 | Phương Sena, Kiều Oanh Mê Làm Đẹp, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 |
| 1.15x | ✗ | — | không bộ 5 nào <= 30,000,000 VNĐ; rẻ nhất có thể: 33,350,000 VNĐ. Giảm slot hoặc tăng ngân sách — hệ thống không âm thầm vượt. |
| 1.3x | ✗ | — | không bộ 5 nào <= 30,000,000 VNĐ; rẻ nhất có thể: 37,700,000 VNĐ. Giảm slot hoặc tăng ngân sách — hệ thống không âm thầm vượt. |
| 1.5x | ✗ | — | không bộ 5 nào <= 30,000,000 VNĐ; rẻ nhất có thể: 43,500,000 VNĐ. Giảm slot hoặc tăng ngân sách — hệ thống không âm thầm vượt. |

## 5. Kiểm tra mức bỏ sót (recall audit)

- Mẫu ngẫu nhiên KOC bị loại ở S2a: **2** người, chấm lại S3.
- Số người lẽ ra vượt ngưỡng giữ: **0** (tỷ lệ 0.0).
- Toàn bộ danh sách loại kèm lý do: `excluded.csv` (23 người).

## 6. Chi phí & hiệu năng
Xem `benchmark.md` (ledger đo thật, lạnh/ấm tách riêng).

- Tổng: 12.8 credit Kalodata · 303,908 token in / 87,469 out (cache 0) · AI $1.8690 · 193 lời gọi ghi ledger.

## 7. Giới hạn & hướng mở rộng

- Không dữ liệu khán giả/giá thuê → 35/100 điểm không tự chấm; kết luận ngân sách theo giả định.
- video/rank thiên video có doanh thu; mẫu 2 video/creator; doanh thu Kalodata là ước tính của họ.
- ASR tiếng Việt đo trên mẫu nhỏ; transcript lỗi → cờ, không kết luận im lặng.
- Chưa làm: Jev judge, Google Sheets, Batch API (−50%), human baseline, vòng phản hồi sau chiến dịch, chồng lấn khán giả thật.
- Mở rộng 500: đổi funnel.candidates + after_2a/after_3, thêm credit; kiến trúc không đổi (mọi tầng parameterized, cache/resume giữ nguyên).