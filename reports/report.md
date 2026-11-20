# Báo cáo đề xuất KOC — kem chống nắng

`run_id=demo_sunscreen` · as_of=2026-11-18 · date_range=2026-10-20~2026-11-18 · seed=42

Models (cấu hình được, không fix cứng): `{"brief": "claude-sonnet-5-5", "screen": "claude-sonnet-5-5", "video": "gemini-3.8-flash", "reason": "claude-sonnet-5-5"}`


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


### Công chúa cam thường (@vanhmakeupcute) — Chủ lực. Điểm đo được cao nhất nhóm chính (40.0/65.0), demo thật, video_gpm cao. Kênh nguội nên cần kiểm chứng.

**Điểm đã đo: 40.0/65.0** (hiệu suất 9.56/25 · nội dung 17.6/25 [phần đo 25.0/25] · hình ảnh 12.84/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `cold_channel` view/follower 0.015 thấp — kênh nguội hoặc follower ảo; `competitor_recent` nhắc đối thủ: Anessa, Cocoon, Neutrogena; `exaggerated_claims` khả năng chống nước và chống bụi mịn thì an toàn luôn đỉnh từ trước đến nay rồi; `exaggerated_claims` mồ hôi chảy ra ướt tóc mà lớp nền nó vẫn bám trên da; chất lượng em này gần như là 2 n mà giá lại cực kỳ là hợp lý; bên màu sốt cả ngày dài

Review có demo thật trên da, kể cả cảnh kiểm tra UV. Cả hai video xem đều chấm demo và hình ảnh 0.85. Ngược lại view/follower thấp và có claim phóng đại, cần duyệt kịch bản.

- Demo trực tiếp: bơm kem lên mặt, chèn màn hình camera UV kiểm tra độ che phủ, so sánh da sau khi thoa kem chống nắng.  
  ↳ bằng chứng: `ev_58b7ef8b12de`
- Hai video xem đều có visual_quality 0.85 và demo_quality 0.85; ad_disclosure_ok true ở cả hai.  
  ↳ bằng chứng: `ev_2af60673ec02, ev_7689c4c849e2`
- video_gpm 558148.92, mức cao nhất trong 5 KOC chính (số đo, chưa kiểm chứng nguồn).  
  ↳ bằng chứng: `ev_564adbe64d4f`
- Đã xem **2/43** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Cờ cold_channel: view/follower 0.015. Median views 3153 nhưng mean 32326.5, phân phối lệch, vài video viral kéo mean.; Claim phóng đại: 'khả năng chống nước và chống bụi mịn thì an toàn luôn đỉnh từ trước đến nay rồi'. Knowledge_accuracy 0.5 và 0.8. Nhắc đối thủ Anessa, Cocoon, Neutrogena.; Mẫu xem 2/43 video. Doanh thu lệch giữa hai nguồn: 95421697.39 và 138628201.44, chưa rõ nguồn nào đúng.
- Giá giả định: 7,000,000 VNĐ · giá trần: **7,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo.; Báo giá thật so với giá trần 7,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Xung đột đối thủ: từng nhắc Anessa, Cocoon, Neutrogena. Hỏi điều khoản độc quyền.; Giải thích chênh lệch doanh thu giữa hai nguồn số liệu.; Duyệt kịch bản trước, tránh claim chống nước tuyệt đối.
- Liên hệ: email=[redacted], tiktok=vanhmakeupcute, zalo=[redacted]

### Phương Sena (@phuongsena) — Chủ lực. Follower cao nhất bộ (261900), đúng ngách chống nắng. Rủi ro nội dung cao nhất, cần kiểm soát kịch bản chặt.

**Điểm đã đo: 41.2/65.0** (hiệu suất 11.91/25 · nội dung 21.6/25 [phần đo 25.0/25] · hình ảnh 7.69/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `exaggerated_claims` Và con này nó là dòng kích trắng luôn; Nó chất nhỏ bằng kích thức vân tử tế bào Nên là khả năng hấp thụ của nó so với những cái dọc này nó là gấp 300%; làm trắng cực kì nhanh luôn Con này có kích trắng mà mọi người; `knowledge_issue` Khuyên tẩy trang xong không cần rửa mặt lại dễ gây bít tắc lỗ chân lông và kích ứng da; Gắn ghép sai lệch hoạt chất chống lão hóa trong kem chống nắng đắt tiền vào công dụng nước tẩy trang; `exaggerated_claims` chỉ dùng trong những rồng kem trồng nắng hàng đầu của thế giới; không cần dựa mặt cũng được luôn

Tần suất đăng đều, thu hút follower mới, ngách chống nắng khớp (niche_fit 0.8). Hai video xem không có demo thoa lên da, có sai kiến thức và claim phóng đại. Chọn được chỉ khi duyệt kịch bản và ép demo thật.

- niche_fit 0.8, style_cluster skincare_science, đúng ngách chống nắng.  
  ↳ bằng chứng: `ev_0740a363cba3`
- Median views 6996, 15.17 bài/tuần, stability 0.535.  
  ↳ bằng chứng: `ev_9c76d173fcc2`
- new_follower_ratio 0.0332; ad_disclosure_ok true ở cả hai video xem.  
  ↳ bằng chứng: `ev_306cb9dcfab1, ev_c1ce67d1dce9, ev_e0e4e6948586`
- Đã xem **2/65** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Demo yếu: demo_quality 0.1 và 0.0. Khung hình cho thấy chỉ cầm giơ sản phẩm, không thoa thử lên da.; Kiến thức: knowledge_accuracy 0.3 ở một video. Khuyên tẩy trang xong không cần rửa mặt lại; gắn sai hoạt chất chống lão hóa vào nước tẩy trang. Claim phóng đại: 'gấp 300%', 'làm trắng cực kì nhanh'.; Quảng cáo toàn một nhãn Lubylab (đối thủ gián tiếp theo niche_signal); ad_ratio 0.323; median ER 0.00775. Mẫu 2/65. Doanh thu lệch giữa hai nguồn: 1579381679.89 và 72923449.64.
- Giá giả định: 7,000,000 VNĐ · giá trần: **7,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo.; Báo giá thật so với giá trần 7,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Xung đột với Lubylab: đang quảng cáo kem chống nắng đối thủ gián tiếp. Hỏi lịch hợp đồng hiện tại.; Yêu cầu quay demo thoa lên da; cấm claim 'gấp 300%', 'làm trắng nhanh'. Thái độ nhận chỉnh sửa kịch bản.; Giải thích chênh lệch doanh thu giữa hai nguồn.
- Liên hệ: tiktok=phuongsena

### Kiều Oanh Mê Làm Đẹp (@kieu_oanh_cosmetic) — Tầm trung. Demo thoa mút tán kem thấy rõ, video_gpm cao. Lỗi kiến thức và thiếu nhãn quảng cáo là điểm cần xử lý.

**Điểm đã đo: 37.85/65.0** (hiệu suất 11.03/25 · nội dung 16.7/25 [phần đo 25.0/25] · hình ảnh 10.12/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `cold_channel` view/follower 0.019 thấp — kênh nguội hoặc follower ảo; `knowledge_issue` Đọc sai tên hoạt chất PDRN thành BDI, Niacinamide thành lia-sinh-a-mai; Dùng bông mút tán kem chống nắng dễ hút bớt sản phẩm làm giảm độ che phủ thực tế; `exaggerated_claims` kem trống nắng mà đẹp hơn cả Kewchon thì chỉ có xeo lắc mới làm được; kiềm dầu cực kì mạnh luôn; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý; `knowledge_issue` Khẳng định mỹ phẩm bôi dạng xịt thấm tới tầng hạ bì là sai cơ chế sinh lý da và sai quy định quảng cáo mỹ phẩm; Tuyên bố sản phẩm bôi ngoài lấp đầy lỗ chân lông vĩnh viễn là phi thực tế; `exaggerated_claims` Dựng chất này nó sẽ đi được đến tầng Ha Bì là tầng thứ 3; Nó lấp đầy đổ chân đông mà nó không cần tái tạo; Hỗ trọ lớp đầy lỗ chân đông luôn; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Có video thoa mút tán kem chống nắng trực tiếp trên da, demo_quality 0.85 ở một video. Kênh nhỏ (119000), mẫu chỉ 10 video. Có lỗi kiến thức và hai video chưa gắn nhãn quảng cáo.

- Video thoa kem chống nắng: dùng mút đệm tán đều trên da, thấy rõ quá trình tán và nâng tone; demo_quality 0.85.  
  ↳ bằng chứng: `ev_06788d1e38cf, ev_ec7c53b44293`
- video_gpm 336493.24, new_follower_ratio 0.0084.  
  ↳ bằng chứng: `ev_7257c9aca60e`
- Median views 2211.0, stability 1.044, mean views 2118.1 (mẫu 10 video).  
  ↳ bằng chứng: `ev_7c3ceafec190`
- Đã xem **2/10** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Lỗi kiến thức: đọc sai tên PDRN, Niacinamide; nói xịt thấm tới hạ bì, lấp đầy lỗ chân lông. Claim 'đẹp hơn cả Kewchon', 'kiềm dầu cực kì mạnh'. Knowledge_accuracy 0.4 và 0.6.; ad_disclosure_ok false ở cả hai video xem (cờ cho người duyệt, không kết luận pháp lý). Số ad_ratio 0.0 trong chỉ số kênh mâu thuẫn với kết quả này.; Cờ cold_channel: view/follower 0.0186. Mẫu 10 video nhỏ. Doanh thu lệch giữa hai nguồn: 813202301.55 và 2968330.56.
- Giá giả định: 6,000,000 VNĐ · giá trần: **6,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo.; Báo giá thật so với giá trần 6,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Cam kết gắn nhãn quảng cáo rõ trong hợp đồng.; Duyệt kịch bản: bỏ claim thẩm thấu hạ bì, lấp lỗ chân lông; kiểm tra tên hoạt chất.; Giải thích chênh lệch doanh thu.
- Liên hệ: tiktok=kieu_oanh_cosmetic

### Cẩm Linh (@calinle) — Tầm trung nhỏ (micro), thử nghiệm. Số đo hiệu suất tốt, sạch cờ, nhưng nội dung chủ yếu thời trang/vlog, chưa có chống nắng.

**Điểm đã đo: 36.12/65.0** (hiệu suất 13.38/25 · nội dung 13.46/25 [phần đo 25.0/25] · hình ảnh 9.28/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.

Không có cờ đỏ. View/follower 0.1171, hình ảnh sạch, không claim phóng đại. Bằng chứng ngách chống nắng không có và demo yếu, nên là ứng viên thử nghiệm, không phải chủ lực.

- View/follower 0.1171, median views 5819.5 trên kênh 49700 follower.  
  ↳ bằng chứng: `ev_44931eb1aaca`
- Hai video xem không có claim phóng đại hay lỗi kiến thức; ad_disclosure_ok true; visual_quality 0.85.  
  ↳ bằng chứng: `ev_92d26b713492, ev_ac0fd89c389d`
- Không có cờ nào từ thuật toán; ad_ratio 0.115, 6.07 bài/tuần.  
  ↳ bằng chứng: `ev_44931eb1aaca`
- Đã xem **2/26** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Lệch ngách: niche_fit 0.2, chủ yếu thời trang/vlog; không thấy nội dung chống nắng. niche_keyword_ratio 0.154.; Demo_quality 0.0 và 0.2 ở hai video xem; chưa có bằng chứng demo mỹ phẩm.; video_gpm 0.0, doanh thu 3275081.24: tín hiệu chuyển đổi mỹ phẩm yếu cho mục tiêu conversion. Mẫu 2/26.
- Giá giả định: 5,000,000 VNĐ · giá trần: **5,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo.; Báo giá thật so với giá trần 5,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Yêu cầu video mẫu/test demo chống nắng trước khi chốt.; Thái độ hợp tác, kinh nghiệm bán mỹ phẩm.
- Liên hệ: email=[redacted], tiktok=calinle

### Khoa Alpha 💪 🇻🇳 (@khoaalpha99) — Tầm trung nhỏ (micro), thử nghiệm. Điểm đo được thấp nhất nhóm chính (33.88/65.0), lệch ngách. Giữ vì view/follower và gpm tốt.

**Điểm đã đo: 33.88/65.0** (hiệu suất 14.56/25 · nội dung 12.38/25 [phần đo 25.0/25] · hình ảnh 6.94/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `er_unusually_high` ER trung vị 0.49 cao bất thường — có thể kênh nhỏ/viral hoặc view ước tính thấp; kiểm tra mẫu video; `ad_no_disclosure` video quảng cáo không gắn nhãn rõ — cờ cho người duyệt, không kết luận pháp lý

Kênh nhỏ có view/follower 0.0796 và video_gpm đáng chú ý. Nội dung chủ đạo là gym/thay đổi ngoại hình, không có chống nắng. Cần test nhỏ.

- Median views 3974.0, view/follower 0.0796 trên kênh 49900 follower.  
  ↳ bằng chứng: `ev_53854d61880e`
- Một video xem có knowledge_accuracy 0.85, hook 0.8, audio 0.9; nhắc test thử vùng da nhỏ lần đầu và vẫn phải chống nắng.  
  ↳ bằng chứng: `ev_3a76ecdacd8d, ev_2dc63e059121, ev_1f6f78b149eb`
- video_gpm 308586.78.  
  ↳ bằng chứng: `ev_eca1f6c4eb5a`
- Đã xem **2/22** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Lệch ngách: niche_fit 0.12, chủ đạo thay đổi ngoại hình, không review chống nắng. niche_keyword_ratio 0.091.; Cờ er_unusually_high (median ER 0.49021); ad_ratio 0.455; ad_disclosure_ok false ở video skincare (không kết luận pháp lý). Một video visual 0.4, audio 0.2, demo 0.0.; Mẫu 2/22. Doanh thu 2517142.38 thấp.
- Giá giả định: 5,000,000 VNĐ · giá trần: **5,000,000 VNĐ** (báo giá vượt trần → chuyển dự phòng)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo, không suy từ nội dung kênh.; Báo giá thật so với giá trần 5,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Kiểm tra ER bất thường (0.49021) và mẫu video.; Cam kết gắn nhãn quảng cáo; xin video thử chống nắng.
- Liên hệ: tiktok=khoaalpha99

### [DỰ PHÒNG] Chang Chăm Chỉ (@changaffiliate) — Dự phòng. Reach và demo mạnh nhất nhóm dự phòng; ad_ratio 0.99 và lệch ngách là rủi ro.

**Điểm đã đo: 38.11/65.0** (hiệu suất 18.09/25 · nội dung 7.46/25 [phần đo 25.0/25] · hình ảnh 12.56/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `ad_saturated` tỷ lệ video quảng cáo 0.99 — uy tín thấp; `exaggerated_claims` hút sạch những bự bẩn sợi bã nhỏ nó muối đi; sờ vào phần mũi Mọi người cảm thấy nó miễn tức thi luôn

Reach lớn: median views 289953.0, view/follower 3.3913, demo_quality 0.85. Video xem là kem nền thỏi và sáp mụn đầu đen, chưa có chống nắng. Dùng thay khi cần reach.

- Median views 289953.0, view/follower 3.3913 trên 100 video.  
  ↳ bằng chứng: `ev_0be6f3121801`
- Demo trực tiếp trên mặt: thoa kem nền thỏi, tán đầu cọ, so sánh nửa mặt; demo_quality 0.85.  
  ↳ bằng chứng: `ev_50ceb83a95d1, ev_49ee22d4990e`
- new_follower_ratio 0.083, video_gpm 381977.67.  
  ↳ bằng chứng: `ev_8f71b2a358b7`
- Đã xem **2/100** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Cờ ad_saturated: ad_ratio 0.99, uy tín thấp. Claim phóng đại ở một video: 'hút sạch', 'miễn tức thì'.; Không có niche_signal trong kho; video xem là kem nền và sáp mụn, chưa chứng minh ngách chống nắng. Median ER 0.00536.; Đăng 23.33 bài/tuần, mẫu 2/100 video. Không có giá trần trong block, cần kiểm tra ngân sách khi thay.
- Giá giả định: 6,000,000 VNĐ · giá trần: áp trần của slot thay thế (dự phòng không nằm trong phân bổ ngân sách hiện tại)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo.; Báo giá thật so với 6,000,000 VNĐ giả định và ngân sách 30,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Cách xử lý lịch quảng cáo dày: có xung đột nhãn hàng cạnh tranh không.; Xin video demo chống nắng.
- Liên hệ: tiktok=changaffiliate

### [DỰ PHÒNG] Mỏ hỗn là tao (@mykimmohon) — Dự phòng. Follower cao nhất (350900), reach lớn. Rủi ro cao nhất: quảng cáo dày, video xem là miếng dán mụn/tóc giả, chuyển đổi chưa chứng minh.

**Điểm đã đo: 34.26/65.0** (hiệu suất 18.38/25 · nội dung 6.6/25 [phần đo 25.0/25] · hình ảnh 9.28/15)
**Chưa đo**: khán giả 25đ (cần ảnh Analytics thật), hợp tác 10đ (giá thật, thái độ, quyền nội dung). Không suy đoán.
Cờ: `ad_saturated` tỷ lệ video quảng cáo 0.91 — uy tín thấp; `exaggerated_claims` Nó hút cái cục ngụng luôn, một lỗ xa quấy luôn; Lò này, lò này là cụ tổ của mấy cái miếng dán mụn luôn trời ơi

Reach lớn (median views 268389.5) và có cảnh demo cận cảnh miếng dán. Quảng cáo chiếm 0.91, nội dung xem không phải chống nắng. Chỉ thay khi cần reach.

- Median views 268389.5, view/follower 0.7649.  
  ↳ bằng chứng: `ev_8bec59221450`
- Demo cận cảnh lột miếng dán hydrocolloid, soi nhân mụn; demo_quality 0.85 ở một video.  
  ↳ bằng chứng: `ev_5a8f3bbae4a3, ev_eac0b669efc7`
- new_follower_ratio 0.0325; ad_disclosure_ok true ở cả hai video xem.  
  ↳ bằng chứng: `ev_89bd98b6461a, ev_3898bdeb5f06, ev_eac0b669efc7`
- Đã xem **2/100** video của KOC (mẫu nhỏ — kết luận hình ảnh/nội dung là chỉ báo).
- Lưu ý: Cờ ad_saturated: ad_ratio 0.91, uy tín thấp. Claim phóng đại: 'cụ tổ của mấy cái miếng dán mụn'.; Video xem là miếng dán mụn và tóc giả, không có chống nắng; không có niche_signal. Một video visual 0.4, demo 0.0.; video_gpm 0.0, doanh thu 426499.66 theo một nguồn; nguồn khác total_revenue 4227559371.92, mâu thuẫn. Mẫu 2/100.
- Giá giả định: 7,000,000 VNĐ · giá trần: áp trần của slot thay thế (dự phòng không nằm trong phân bổ ngân sách hiện tại)
- Xác minh trước chốt: Ảnh Analytics khán giả nữ 18-30 VN. Chưa đo.; Báo giá thật so với 7,000,000 VNĐ giả định và ngân sách 30,000,000 VNĐ.; Quyền sử dụng nội dung và Spark Ads.; Giải thích chênh lệch doanh thu và video_gpm 0.0.; Xin video demo chống nắng; thái độ hợp tác.
- Liên hệ: tiktok=mykimmohon

**Phương án thay thế** (chênh lệch điểm so với phương án 1):
- PA2: Công chúa cam thường, Phương Sena, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 · điểm 2.8567 (Δ -0.0517) · giá 30,000,000
- PA3: Phương Sena, Kiều Oanh Mê Làm Đẹp, Chang Chăm Chỉ, Cẩm Linh, Khoa Alpha 💪 🇻🇳 · điểm 2.8236 (Δ -0.0848) · giá 29,000,000

Hoán đổi 1 người (phương án 1): Công chúa cam thường → Chang Chăm Chỉ (Δ điểm -0.0848); Phương Sena → Chang Chăm Chỉ (Δ điểm -0.1032); Kiều Oanh Mê Làm Đẹp → Chang Chăm Chỉ (Δ điểm -0.0517); Cẩm Linh → không có phương án tốt hơn; Khoa Alpha 💪 🇻🇳 → không có phương án tốt hơn

## 4. Ngân sách (GIẢ ĐỊNH — không phải báo giá)

- Tổng giá giả định bộ 5: **30,000,000 VNĐ** / ngân sách 30,000,000
- **Hệ số giá tối đa còn khả thi: 1.0** (giá thật cao hơn mức này → vượt ngân sách, dùng phương án thay thế)
- Bảng giá theo tier là minh họa; chỉ tỷ lệ tương đối có ý nghĩa. Điểm chất lượng KHÔNG dùng giá.

| price_scale | khả thi | tổng giá (VNĐ) | bộ 5 tối ưu / ghi chú |
|---|---|---|---|
| 0.7x | ✓ | 21,700,000 | Công chúa cam thường, Phương Sena, Kiều Oanh Mê Làm Đẹp, Chang Chăm Chỉ, Cẩm Linh |
| 0.85x | ✓ | 26,350,000 | Công chúa cam thường, Phương Sena, Kiều Oanh Mê Làm Đẹp, Chang Chăm Chỉ, Cẩm Linh |
| 1.0x | ✓ | 30,000,000 | Công chúa cam thường, Phương Sena, Kiều Oanh Mê Làm Đẹp, Cẩm Linh, Khoa Alpha 💪 🇻🇳 |
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

- Tổng: 12.8 credit Kalodata · 472,678 token in / 44,154 out (cache 0) · AI $0.8241 · 194 lời gọi ghi ledger.

## 7. Giới hạn & hướng mở rộng

- Không dữ liệu khán giả/giá thuê → 35/100 điểm không tự chấm; kết luận ngân sách theo giả định.
- video/rank thiên video có doanh thu; mẫu 2 video/creator; doanh thu Kalodata là ước tính của họ.
- ASR tiếng Việt đo trên mẫu nhỏ; transcript lỗi → cờ, không kết luận im lặng.
- Chưa làm: Jev judge, Google Sheets, Batch API (−50%), human baseline, vòng phản hồi sau chiến dịch, chồng lấn khán giả thật.
- Mở rộng 500: đổi funnel.candidates + after_2a/after_3, thêm credit; kiến trúc không đổi (mọi tầng parameterized, cache/resume giữ nguyên).