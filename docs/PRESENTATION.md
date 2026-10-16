# Kịch bản trình bày 10 phút: Team Cheby (VinFast DMS)

## Trước khi lên (checklist 9 mục)

| # | Mục | Trạng thái |
|---|---|---|
| 1 | Chạy trên đúng máy demo, đã thử webcam ở phòng demo | `python scripts/live_check.py` **tại phòng demo**, xem `brightness_median` > 45 và FPS ≥ 20 |
| 2 | Có video dự phòng | `python app.py --save-video`, diễn đủ kịch bản bên dưới, file nằm ở `recordings/demo_*.mp4`. Copy ra Desktop |
| 3 | Một con số đo, nói được cách đo | độ trễ 7.6 ms p50; recall và báo động giả mỗi phút từ `evaluate.py` |
| 4 | Một ca lỗi kèm lý do | kính râm (bỏ sót) + lỗi PERCLOS đã sửa |
| 5 | ≥ 2 trụ cột và vị trí | bảng mục 3 trong README |
| 6 | Không dùng dữ liệu thật | chỉ mặt mình, `recordings/` không đẩy lên repo |
| 7 | Vì sao chọn cách này | phần hỏi đáp bên dưới |
| 8 | Người dùng là ai, được gì | tài xế Xanh SM ca đêm + bộ phận an toàn đội xe |
| 9 | Ước lượng tác động | khoảng 20 va chạm có thương tích/năm trên 20.000 xe (khoảng 3–116) |

Mang theo: kính râm (cho ca lỗi), điện thoại (cảnh cúi nhìn điện thoại).

## 1 phút: bài toán

> "Tài xế taxi điện Xanh SM chạy ca 10–12 tiếng, nhiều người chạy đêm. Buồn ngủ thì mình không tự biết được: vi giấc ngủ 2 giây ở 60 km/h là 33 mét không có người lái. AAA ước tính 17.6% vụ tai nạn chết người ở Mỹ có tài xế buồn ngủ. Từ tháng 7 năm nay, EU bắt buộc mọi xe mới phải có cảnh báo xao nhãng, và VinFast đang bán xe ở châu Âu. Sản phẩm của em là một hệ thống giám sát tài xế chạy trên camera thường, cảnh báo ngay trong xe."

## 4 phút: demo trực tiếp (`python app.py`)

1. **Hiệu chuẩn (15 s):** "3 giây đầu hệ thống học EAR lúc mở mắt và tư thế nhìn đường *của riêng em*. Ngưỡng nhắm là 0.65 lần mức đó, vì mắt mỗi người khác nhau." Chỉ vào dòng `EAR ... (nguong ...)`.
2. **Chớp mắt (15 s):** chớp tự nhiên → vẫn `TINH TAO`, bộ đếm chớp mắt tăng. "Chớp mắt dưới 0.5 s không phải buồn ngủ."
3. **Nhắm mắt 3 s:** còi kêu và viền đỏ hiện sau đúng 1 s. Chỉ vào biểu đồ EAR góc phải: đường EAR rơi xuống dưới đường ngưỡng.
4. **Quay đầu sang cửa sổ 4 s:** `MAT TAP TRUNG` sau 2 s. "Góc này tính bằng solvePnP, so với tư thế lúc hiệu chuẩn chứ không phải góc tuyệt đối."
5. **Cúi nhìn điện thoại 4 s:** `MAT TAP TRUNG` (pitch).
6. **Lấy tay che camera, hoặc quay lưng về phía đèn:** `KHONG CHAC CHAN (thieu sang)`. "Khi không thấy rõ thì hệ thống nói là không chắc, chứ không nói là tỉnh táo."
7. **Mời giám khảo ngồi vào** → bấm `c` để hiệu chuẩn lại cho người mới, rồi cho giám khảo tự nhắm mắt và quay đầu. (Đây là "đầu vào do giám khảo đưa ra" của tiêu chí 2.)

Nếu demo hỏng: `python app.py --source recordings/demo_<...>.mp4` và **nói rõ đây là video quay sẵn**.

## 2 phút: số đo, ca lỗi, trụ cột, tác động

- **Số đo:** "Độ trễ từ lúc đọc frame tới khi ra quyết định là 7.6 ms (p50), đo cho từng frame bằng perf_counter, ở 30 FPS. Trên kịch bản có nhãn: [recall sự kiện, báo động giả mỗi phút từ reports/main_*/metrics.md]."
- **Ca lỗi:** đeo kính râm rồi nhắm mắt → **không có cảnh báo**. "MediaPipe vẫn vẽ mí mắt dù không thấy mắt, vì model đã học hình dạng mặt trung bình nên đoán là mắt đang mở. Cổng chất lượng không bắt được vì vùng mặt vẫn sáng và nét. Xe thật dùng camera hồng ngoại để xuyên qua kính." Thêm lỗi PERCLOS tìm ra khi chạy thật và đã sửa.
- **Trụ cột:** Hình học (solvePnP 13 điểm cứng), Thời gian (ngưỡng theo giây, Kalman theo dt thật), Bất định (UNCERTAIN), và cả Biểu diễn, Dữ liệu, Bằng chứng.
- **Tác động:** "20.000 xe × 3% va chạm có thương tích/năm × 10% do buồn ngủ × giảm 33% ≈ 20 vụ/năm. Giả định yếu nhất là tỉ lệ va chạm, và GSM có sẵn số liệu thật để thay."

## 3 phút: hỏi đáp (chuẩn bị sẵn)

**Vì sao EAR mà không dùng luôn blendshape `eyeBlink` của MediaPipe?**
EAR giải thích được và hiệu chuẩn được cho từng người, còn blendshape là hộp đen với ngưỡng cố định 0.5. `evaluate.py` so cả hai trên cùng dữ liệu có nhãn. [điền kết quả F1 của hai cách].

**Vì sao ngưỡng 1 s cho buồn ngủ, 2 s cho xao nhãng?**
Chớp mắt bình thường 0.1–0.4 s, nên nhắm ≥ 1 s đã là vi giấc ngủ. Euro NCAP coi nhìn đi chỗ khác ≥ 3 s là xao nhãng dài. Demo dùng 2 s để thấy nhanh. Đây là đánh đổi giữa báo sớm và báo động giả.

**Vì sao tính theo giây mà không đếm frame?**
FPS webcam dao động 15–30 tuỳ ánh sáng. Nếu đếm 30 frame thì ở 15 FPS phải nhắm 2 s mới báo. Có test `test_fps_independence`.

**Kalman để làm gì nếu MediaPipe đã mượt?**
Đo thật thấy Kalman không giảm rung nhiều (0.19° → 0.19° yaw), và em đã ghi lại điều này trong README. Giá trị thật của nó là dự đoán góc khi mất mặt dưới 0.5 s, và cho độ bất định tăng dần khi không có đo đạc. Không lọc EAR vì sẽ làm mất chớp mắt và làm trễ cảnh báo.

**Không hiệu chuẩn camera thì solvePnP có sai không?**
Benchmark cho thấy sai f ±30% chỉ làm góc lệch dưới 1.5°, trong khi ngưỡng là 30°. Riêng khoảng cách thì sai đúng bằng tỉ lệ sai f. Có sẵn `calibrate_camera.py` (bàn cờ) nếu cần.

**Vì sao chọn 13 điểm cứng cho solvePnP?**
Cằm và môi di chuyển khi ngáp. Nếu dùng cằm thì ngáp sẽ bị tính thành gật đầu, dẫn tới báo xao nhãng giả.

**Vì sao trừ tư thế hiệu chuẩn?**
Camera DMS thật đặt ở cột lái nhìn từ dưới lên, nên khi nhìn đường góc tuyệt đối đã khoảng −20°. Có test `test_distraction_relative_to_neutral_pose`.

**Hệ thống sai khi nào?**
Kính râm, tay che mặt, cúi nhìn đồng hồ xe (EAR giảm giống như nhắm mắt), ban đêm khi chỉ có camera RGB. Chi tiết ở README mục 5.

**Đã chứng minh tới đâu?**
1 người, 1 webcam, trong nhà, buồn ngủ là đóng vai. Chưa chứng minh được gì cho buồn ngủ thật, ban đêm hay nhiều người khác nhau.
