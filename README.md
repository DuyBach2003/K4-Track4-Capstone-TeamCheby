# VinFast DMS: Giám sát tài xế buồn ngủ và mất tập trung bằng webcam

**Team Cheby** (làm cá nhân, có sự cho phép của lab coach): Đoàn Duy Bách, MSSV 2A202602515
Capstone Track 4, Day 28. Đơn vị Vin: **VinFast / Xanh SM (GSM)**

Hệ thống nhìn mặt tài xế qua một camera RGB thường và đưa ra một trong năm trạng thái, mỗi frame một lần, kèm âm thanh cảnh báo:

| Trạng thái | Khi nào | Phản ứng |
|---|---|---|
| `DROWSY` | cả hai mắt nhắm liên tục ≥ 1.0 s (vi giấc ngủ). "Nhắm" khi EAR cá nhân hoá **và** blendshape của model cùng đồng ý | còi + viền đỏ nhấp nháy |
| `DISTRACTED` | **hướng nhìn** (góc đầu + góc mắt tính từ mống mắt) lệch khỏi tư thế nhìn đường > 30° ngang, hoặc cúi đầu > 20°, kéo dài ≥ 2.0 s | còi + viền cam |
| `FATIGUE` | PERCLOS > 15% trong 30 s, hoặc ≥ 2 lần ngáp trong 2 phút | nhắc nghỉ ngơi |
| `UNCERTAIN` | thiếu sáng, ảnh mờ, mất mặt, quay đầu quá 40° | **báo rõ là không chắc**, không im lặng nói "tỉnh táo" |
| `OK` | còn lại | |

## 1. Bài toán và người dùng

**Người dùng chính:** tài xế taxi điện Xanh SM chạy ca đêm. Đội xe là ô tô điện VinFast, ca lái thường 10–12 giờ. Tài xế là người nhận cảnh báo ngay trong xe. **Người dùng thứ hai:** bộ phận an toàn đội xe của GSM. Họ cần biết xe nào, ca nào, giờ nào hay có cảnh báo để sắp xếp ca và cho nghỉ, thay vì chỉ biết sau khi đã xảy ra va chạm.

**Nỗi đau:** buồn ngủ không tự cảm nhận được. Một lần vi giấc ngủ 2 giây ở tốc độ 60 km/h là xe đi 33 m mà không có người lái. Nghiên cứu của AAA Foundation ước tính **17.6% vụ tai nạn chết người ở Mỹ giai đoạn 2017–2021 có tài xế buồn ngủ**. Thống kê chính thức của cảnh sát thấp hơn nhiều, vì sau va chạm rất khó xác định tài xế có buồn ngủ hay không.

**Vì sao đúng lúc với VinFast:** từ **7/7/2026**, EU bắt buộc mọi xe mới đăng ký phải có hệ thống cảnh báo xao nhãng ADDW (Regulation (EU) 2019/2144). VinFast đang bán xe tại châu Âu, nên giám sát tài xế bằng camera là yêu cầu bắt buộc chứ không còn là tính năng thêm.

## 2. Chạy thử

```bash
git clone https://github.com/DuyBach2003/K4-Track4-Capstone-TeamCheby.git
cd K4-Track4-Capstone-TeamCheby
python3.12 -m venv .venv && source .venv/bin/activate      # MediaPipe chưa hỗ trợ Python 3.13+
pip install -r requirements.txt

python app.py                        # demo trực tiếp trên webcam
python app.py --source video.mp4     # chạy lại video quay sẵn (video dự phòng)
python app.py --save-video           # vừa demo vừa ghi video dự phòng có HUD
```

Phím tắt: `c` hiệu chuẩn lại (khi đổi người lái), `m` ẩn/hiện mốc mặt, `s` tắt/bật còi, `r` bắt đầu/dừng ghi video, `space` tạm dừng, `q` thoát.
Model `models/face_landmarker.task` (3.7 MB, Apache 2.0) đã có sẵn trong repo nên chạy không cần mạng.

3 giây đầu là **hiệu chuẩn**: nhìn thẳng, mở mắt bình thường. Mọi ngưỡng sau đó là ngưỡng riêng của người này (xem mục 3).

| Lệnh | Để làm gì |
|---|---|
| `python scripts/live_check.py` | kiểm tra trên đúng máy và phòng demo: FPS, độ trễ, độ sáng, độ rung góc đầu. Chỉ lưu số, không lưu ảnh |
| `python scripts/record_protocol.py --protocol main` | thu video có nhãn theo kịch bản (lời nhắc được đọc to bằng giọng tiếng Việt, nên người đóng vai không cần nhìn màn hình) |
| `python scripts/evaluate.py recordings/<file>.mp4` | chạy lại video qua đúng pipeline của demo, so với nhãn, xuất `reports/<file>/metrics.md` và `timeline.png` |
| `python scripts/bench_headpose.py` | benchmark sai số solvePnP theo nhiễu mốc và sai tiêu cự |
| `python scripts/calibrate_camera.py` | (tuỳ chọn) hiệu chuẩn webcam bằng bàn cờ để có ma trận K thật |
| `pytest` | 22 test cho hình học, hướng nhìn, Kalman và máy trạng thái |

## 3. Kiến trúc và các trụ cột Track 4

```
 webcam 30 Hz ──► MediaPipe FaceLandmarker ──► 478 mốc + 52 blendshape ──┬─► EAR trái/phải, MAR, eyeBlink       (BIỂU DIỄN)
 (t thật)          pretrained, CPU 5.7 ms        (HỌC)                     ├─► solvePnP 13 điểm cứng → góc đầu, cm (HÌNH HỌC)
                                                                           └─► mống mắt + nhãn cầu 12 mm → góc mắt (HÌNH HỌC)
                                                                          │  hướng nhìn = góc đầu + góc mắt
              chất lượng vùng mặt: sáng, nét, |yaw| ──► UNCERTAIN    Kalman theo dt thật               (BẤT ĐỊNH, THỜI GIAN)
                                                                          ▼
                              máy trạng thái theo GIÂY: hiệu chuẩn → OK / FATIGUE / DROWSY / DISTRACTED     (THỜI GIAN)
                                                                          ▼
                              HUD + còi    │    log CSV từng frame → replay → evaluate.py                 (DỮ LIỆU, BẰNG CHỨNG)
```

Dùng 7/7 trụ cột. Mỗi trụ cột ghi rõ nằm ở file nào và vì sao chọn cách đó thay vì cách khác:

| Trụ cột | Nằm ở đâu | Làm gì, vì sao chọn cách này |
|---|---|---|
| **1. Học** | [dms/pipeline.py](dms/pipeline.py) | MediaPipe FaceLandmarker pretrained: 478 mốc 3D và 52 blendshape. Hai giờ không đủ để train, và model này chạy CPU 5.7 ms/frame. Mắt chỉ được coi là nhắm khi blendshape `eyeBlink` của model (ở **cả hai mắt**) và EAR hình học cùng đồng ý (mục 5.2). [evaluate.py](scripts/evaluate.py) so sánh hệ thống với cách chỉ dùng blendshape. Không dùng dlib 68 điểm vì nó cần thêm bộ phát hiện mặt riêng và không có toạ độ 3D hay blendshape để đối chiếu. |
| **2. Hình học** | [dms/head_pose.py](dms/head_pose.py) | `cv2.solvePnP` với **13 điểm cứng** lấy từ mô hình mặt chuẩn của MediaPipe (đơn vị cm). Cố ý bỏ cằm, môi và mí mắt, vì các điểm này di chuyển khi ngáp hay nhắm mắt và sẽ làm solvePnP tưởng là đầu đang gật. Mô hình tính bằng cm nên `tvec` cho luôn khoảng cách tới camera. Chưa có hiệu chuẩn nên tạm lấy f ≈ 0.85·W (webcam laptop có FOV ngang khoảng 60–70°). Benchmark cho thấy sai f ±30% chỉ làm sai góc dưới 1.5°, nhưng làm sai khoảng cách khoảng 30% (mục 4.2). **Góc mắt** ([dms/features.py](dms/features.py)): mống mắt lệch bao nhiêu so với giữa hai khoé, tính theo bề rộng khe mắt (~30 mm), rồi đổi ra góc bằng mô hình nhãn cầu bán kính ~12 mm: sin θ = lệch × 30/12. Tỉ số này không đổi khi mặt xa hay gần. Lý do cần (mục 5.2): người có thể quay đầu mà mắt vẫn nhìn đường, hoặc chỉ liếc mắt mà đầu đứng yên. |
| **3. Bất định** | [dms/quality.py](dms/quality.py), [dms/state.py](dms/state.py) | Mỗi frame đo độ sáng và độ nét (phương sai Laplacian) của vùng mặt, cộng thêm \|yaw\| và thời gian mất mặt. Khi đầu vào không tin được, hệ thống **ngừng đếm thời gian nhắm mắt** (để ngược sáng không gây báo động giả) và hiện `UNCERTAIN` kèm lý do. Hệ thống an toàn phải "fail loud". Khi quay đầu quá 20° thì chỉ tin EAR của mắt gần camera, vì mắt xa bị co ngắn. |
| **4. Biểu diễn** | [dms/features.py](dms/features.py) | Mặt tài xế được rút gọn còn vài con số có nghĩa: EAR (Soukupová & Čech 2016), MAR, góc yaw/pitch/roll **so với tư thế nhìn đường của chính người đó** (đo lúc hiệu chuẩn). Camera thật đặt ở cột lái nhìn mặt từ dưới lên, nên góc tuyệt đối không dùng được. Ngưỡng nhắm mắt = 0.65 × EAR lúc mở của từng người, vì EAR khác nhau giữa người (mắt một mí khoảng 0.22, mắt to khoảng 0.33). |
| **5. Thời gian** | [dms/state.py](dms/state.py), [dms/kalman.py](dms/kalman.py) | Mọi ngưỡng tính theo **giây từ timestamp thật**, không đếm frame. Webcam chạy 15–30 FPS tuỳ ánh sáng, mà "nhắm 1 s" phải đúng ở cả hai mức (có test `test_fps_independence`). Có hysteresis mở/nhắm (0.65/0.75), và hysteresis 5° cho trạng thái "nhìn đi chỗ khác" (thiếu nó thì một frame dao động quanh 30° sẽ đặt lại đồng hồ 2 s; đã xảy ra ở dữ liệu v1). Kalman vận tốc không đổi cho góc đầu, F và Q tính lại theo dt mỗi frame, chạy `predict()` khi mất mặt dưới 0.5 s. **Không lọc EAR**, vì chớp mắt chỉ 100–400 ms và làm mượt sẽ xoá chớp mắt và làm trễ cảnh báo. Đo độ trễ từ lúc đọc frame tới khi ra quyết định cho từng frame. |
| **6. Dữ liệu** | [dms/io_utils.py](dms/io_utils.py), [scripts/record_protocol.py](scripts/record_protocol.py) | Log CSV từng frame, 35 cột. Thu video có nhãn theo kịch bản cố định, nhãn chính là lời nhắc **được đọc to**, kèm timestamp thật từng frame. **Replay** chạy qua đúng pipeline của demo, nên kết quả lặp lại được. |
| **7. Bằng chứng** | [scripts/evaluate.py](scripts/evaluate.py), [reports/](reports/) | Tính precision/recall theo frame, tỉ lệ bắt sự kiện và độ trễ cảnh báo, số báo động giả mỗi phút, độ trễ p50/p95. Có cả ca lỗi và giới hạn (mục 4, 5). |

## 4. Số đo

### 4.1 Trên máy demo thật (MacBook Air, webcam tích hợp, 1280×720)

Lấy từ [`reports/live_check/`](reports/live_check/), chạy lại bằng `python scripts/live_check.py --seconds 15`:

| Số đo | Giá trị |
|---|---|
| FPS đầu vào thực tế | **29.9** |
| Độ trễ đọc frame → quyết định | **p50 7.6 ms, p95 10.2 ms** (riêng model: 5.7 ms) |
| Frame thấy mặt (ngồi trước máy, đèn phòng) | 100% |
| EAR lúc mở mắt sau hiệu chuẩn | 0.28 |
| Khoảng cách mặt–camera ước lượng | 59 cm |
| Độ rung yaw giữa 2 frame liên tiếp: thô → Kalman | 0.19° → 0.19° |
| Độ rung pitch giữa 2 frame liên tiếp: thô → Kalman | 0.11° → 0.07° |

Cách đo độ trễ: lấy `perf_counter()` ngay sau `cap.read()`, rồi lấy lại lúc có trạng thái. Con số này **không gồm** thời gian phơi sáng và bộ đệm của camera (thường thêm 30–60 ms), vì không đo được từ phía phần mềm. Dù vậy vẫn rất nhỏ so với ngưỡng cảnh báo 1 s, nên **phần quyết định thời điểm báo là ngưỡng thời gian chủ động chọn, không phải tốc độ tính toán**.

**Một giả định bị số đo bác bỏ:** ban đầu mình đặt Kalman với giả định góc đầu thô rung 1–3°. Đo thật chỉ thấy khoảng 0.2°/frame, vì MediaPipe ở chế độ VIDEO đã tự làm mượt mốc. Nghĩa là Kalman **gần như không giúp làm mượt**. Giá trị thật của nó là dự đoán tiếp khi mất mặt ngắn hạn (che tay, chớp sáng) và cung cấp độ bất định `pose_std` tăng dần khi không có đo đạc.

### 4.2 Hình học: solvePnP sai bao nhiêu độ

Từ [`reports/headpose_bench/`](reports/headpose_bench/README.md). Dùng dữ liệu tổng hợp với góc thật đã biết, yaw −60..60°, pitch −30..30°, 20 lần lặp mỗi góc:

| Điều kiện | yaw MAE | pitch MAE | sai khoảng cách |
|---|---|---|---|
| nhiễu mốc 1 px | 0.25° | 0.33° | 0.3% |
| nhiễu mốc 2 px | 0.53° | 0.82° | 0.8% |
| nhiễu 1 px, **f sai −30%** | 0.52° | 1.38° | **31%** |
| nhiễu 1 px, f sai +15% | 0.30° | 0.52° | 15.6% |

Kết luận: cảnh báo xao nhãng dùng ngưỡng 30° nên **không cần hiệu chuẩn camera**. Số đo khoảng cách thì chỉ đúng tới mức tiêu cự đúng. Muốn dùng con số cm thì phải chạy `calibrate_camera.py`.

### 4.3 Trên dữ liệu có nhãn

Mỗi bản quay được chấm bằng `evaluate.py`. Kịch bản `main` (90 s) gồm 3 lần nhắm mắt (4 s, 3 s, 4 s), 3 lần nhìn đi chỗ khác (trái, phải, cúi xem điện thoại), 1 lần ngáp, 1 lần nhắm nhanh 0.8 s và chớp mắt tự nhiên (hai việc cuối không được báo). Có bốn số đo: (a) precision/recall nhắm mắt theo frame; (b) bao nhiêu sự kiện được báo và trễ bao lâu; (c) báo động giả mỗi phút trong các đoạn bình thường; (d) độ trễ xử lý.

**Lần thu 1 (v1), hệ thống v1** ([reports/v1_main_*](reports/v1_main_bach_20261016_192527/metrics.md), [reports/v1_failure_*](reports/v1_failure_bach_20261016_192721/metrics.md)):

| Số đo | main | failure |
|---|---|---|
| Nhắm mắt theo frame, F1 (P / R) | 0.67 (0.61 / 0.73) | 0.61 (0.44 / 1.00) |
| `DROWSY` bắt được | 3/3 | 1/1 |
| `DISTRACTED` bắt được | **0/3** | **0/1** |
| Báo động giả trong đoạn bình thường | 0 | 0 |
| `DROWSY` sai trong các đoạn "ANY" | cúi xem điện thoại | tay che một mắt |
| Độ trễ xử lý p50 (replay) | 3.9 ms | 4.0 ms |

Phân tích ở mục 5.2 cho thấy một nửa số lỗi là do **kịch bản thu sai**, nửa còn lại là **lỗi thiết kế**. Từ đó có hệ thống v2 (EAR và blendshape cùng đồng ý, hướng nhìn = đầu + mắt, hysteresis 5°) và kịch bản v2 (lời nhắc đọc to).

**Hệ thống v2 chạy lại trên chính dữ liệu v1** ([reports/main_*](reports/main_bach_20261016_192527/metrics.md), [reports/failure_*](reports/failure_bach_20261016_192721/metrics.md)). **Không độc lập**, vì v2 được thiết kế sau khi đã xem dữ liệu này:

| Số đo | main v1 → v2 | failure v1 → v2 |
|---|---|---|
| Nhắm mắt F1 (P / R) | 0.67 → **0.74** (0.76 / 0.72) | 0.61 → **0.68** (0.51 / 1.00) |
| Chỉ blendshape, F1 (đối chứng) | 0.77 | 0.76 |
| `DROWSY` sai do cúi điện thoại / tay che mắt | có → **không** | có → **không** |
| `DROWSY` bắt được | 3/3 | 1/1 |

Precision thấp chủ yếu do nhãn lệch giờ: ở v1 người đóng vai nhắm mắt muộn khoảng 2 s và mở muộn khoảng 0.5 s so với lời nhắc, nên frame "đang nhắm" rơi vào đoạn nhãn "mở".
**Một kết quả không như kỳ vọng:** chỉ dùng blendshape có F1 bằng hoặc cao hơn hệ thống kết hợp. Trên dữ liệu này, EAR chưa chứng minh được là cần thiết. Mình giữ EAR vì nó cá nhân hoá được và giải thích được, nhưng đây là lựa chọn thiết kế, không phải kết luận từ số đo.

**Lần thu 2 (v2, kiểm chứng độc lập):** _đang chờ thu bằng kịch bản đọc to._

## 5. Ca lỗi

### 5.1 Lỗi tìm ra khi chạy webcam thật, đã sửa

Lần chạy đầu trên webcam, hệ thống báo `FATIGUE` ngay sau khi hiệu chuẩn xong, trong khi người ngồi hoàn toàn tỉnh táo (128/255 frame sau hiệu chuẩn).
**Nguyên nhân:** PERCLOS (tỉ lệ thời gian nhắm mắt) được tính trên toàn bộ lịch sử hiện có. Ngay sau hiệu chuẩn, lịch sử chỉ dài vài giây, nên 2–3 lần chớp mắt (mỗi lần khoảng 0.3 s) đã vượt 15%. Đây là lỗi **thống kê trên mẫu quá nhỏ**, không phải lỗi model.
**Sửa:** chỉ kết luận mệt mỏi khi đã có ít nhất 15 s lịch sử (`perclos_min_history_s`). Có test hồi quy `test_perclos_needs_enough_history_before_fatigue`. Chạy lại 15 s: 0 frame `FATIGUE`.

### 5.2 Ca lỗi thật trên dữ liệu có nhãn (lần thu 1)

| Ca | Hệ thống v1 làm gì | Vì sao | Xử lý ở v2 |
|---|---|---|---|
| **Cúi xem điện thoại** | báo `DROWSY` (56% frame bị coi là nhắm) thay vì `DISTRACTED` | Khi nhìn xuống, mí mắt trên hạ xuống thật, nên EAR giảm giống như nhắm mắt. Riêng blendshape `eyeBlink` của model vẫn thấy mắt mở (0.30, trong khi lúc nhắm thật là 0.72). | Coi là nhắm chỉ khi EAR **và** blendshape cùng đồng ý: frame bị coi là nhắm giảm từ 56% xuống 6% (bảng từng đoạn trong metrics.md), hết `DROWSY` giả. **Vẫn chưa bắt được là xao nhãng**: đầu chỉ cúi −14°, ngưỡng là −20°, phần lớn việc nhìn xuống là do mắt. Góc mắt theo chiều dọc không đo được, vì mống mắt dịch xuống cả khi nhắm mắt. |
| **Tay che một mắt** | báo `DROWSY` | Tay đè lên mặt làm cả hai mắt nheo lại (EAR 0.20 / 0.17). Blendshape trung bình hai mắt cũng tăng. | Buồn ngủ là nhắm **cả hai** mắt, nên dùng min của blendshape hai mắt: hết `DROWSY` giả. |
| **"Quay đầu sang trái/phải" không được báo (0/3)** | yaw đầu chỉ 20° và 31°, chưa vượt 30° liên tục 2 s | Xem ảnh và mống mắt thì **mắt liếc ngược lại về màn hình** (−16°) để đọc lời nhắc và đồng hồ đếm ngược. Hướng nhìn thật chỉ khoảng 3° và 17°. Nhãn "away" sai, lỗi nằm ở **kịch bản thu**. Ngoài ra đồng hồ 2 s bị đặt lại mỗi khi yaw dao động dưới 30°. | Kịch bản v2 đọc to lời nhắc. Hệ thống đo **hướng nhìn** (đầu + mắt) thay vì chỉ góc đầu: quay đầu mà mắt vẫn nhìn đường thì không báo (đúng). Thêm hysteresis 5°. |
| Nhắm mắt muộn khoảng 2 s so với lời nhắc | độ trễ cảnh báo đo được 1.7–3.3 s thay vì khoảng 1 s theo thiết kế | Người đóng vai phải đọc xong lời nhắc trên màn hình rồi mới nhắm được. | Kịch bản v2 đọc to. |

### 5.3 Ca lỗi đã biết nhưng chưa có bằng chứng

| Ca | Dự đoán | Tình trạng |
|---|---|---|
| **Kính râm**, nhắm mắt sau kính | Bỏ sót `DROWSY`, vì MediaPipe vẫn "đoán" mí mắt theo hình mặt trung bình. Camera DMS thật dùng hồng ngoại 940 nm để xuyên qua kính. | **Chưa thử**: lúc thu 1 không có kính râm (xem lại video thì không đeo). |
| Tắt đèn, ngược sáng | `UNCERTAIN (LOW_LIGHT)`, không báo động giả (có test) | Chưa thử thật: thu trong lớp nên không tắt đèn được. |
| Quay đầu > 60° | `DISTRACTED`, EAR bị đánh dấu không tin được | Lúc thu 1 người đóng vai không quay đủ. Kịch bản failure v2 có lại đoạn này. |

## 6. Giới hạn của những gì đã chứng minh

- **Chỉ thử trên 1 người** (tác giả), 1 webcam, ánh sáng trong nhà. Chưa có bằng chứng cho người khác, cho mắt một mí hay cho ánh sáng ban đêm trong xe.
- **Camera RGB**, không phải hồng ngoại. Ban đêm thật trong xe thì hệ thống sẽ phần lớn ở trạng thái `UNCERTAIN`.
- Nhãn lấy từ lời nhắc. Thời gian phản ứng (~0.5 s) được loại bằng cách bỏ 0.7 s đầu mỗi đoạn, nên chưa phải nhãn chính xác tới từng frame. Ở lần thu 1, người đóng vai trễ tới khoảng 2 s.
- **Mọi thay đổi của v2 được chọn sau khi xem dữ liệu lần thu 1**, nên số v2 trên dữ liệu đó là lạc quan. Chỉ lần thu 2 mới là kiểm chứng độc lập.
- Cúi nhìn điện thoại mà đầu cúi ít (phần lớn là mắt nhìn xuống) thì **chưa bắt được** (mục 5.2).
- **Đóng vai buồn ngủ không phải buồn ngủ thật.** Nhắm mắt có chủ đích dứt khoát hơn vi giấc ngủ thật (mắt sụp từ từ, nửa nhắm nửa mở). PERCLOS dùng cửa sổ 30 s thay cho chuẩn 60 s để demo được trong 10 phút.
- Khoảng cách đã thấy chạy: 40–60 cm (khoảng cách ngồi trước laptop). Chưa thử xa hơn. Góc quay tin được: \|yaw\| ≤ 40°.
- Độ trễ đo được không gồm độ trễ phơi sáng và bộ đệm của camera.
- Che camera hoặc không có người: chỉ hiện `UNCERTAIN (NO_FACE)`, chưa có còi riêng.

## 7. Tác động nếu triển khai ở Vin

**Phép tính cho đội xe Xanh SM.** Mỗi tham số đều ghi rõ nguồn hoặc ghi rõ là giả định:

| Tham số | Giá trị dùng | Khoảng | Nguồn |
|---|---|---|---|
| Số ô tô của GSM | 20.000 | – | trang tuyển dụng GSM (chưa rõ thời điểm cập nhật) |
| Va chạm có thương tích / xe / năm | 3% | 1–5% | **giả định** (chưa có số liệu công khai cho taxi VN) |
| Tỉ lệ va chạm có tài xế buồn ngủ | 10% | 7–17.6% | AAA Foundation: 17.6% vụ chết người, ~7% tổng số vụ (Mỹ) |
| Mức giảm nhờ cảnh báo trong xe | 33% | 20–66% | Seeing Machines × Monash (2011–2015): **sự kiện mệt mỏi** giảm 66% chỉ với cảnh báo trong cabin, 95% khi có thêm phản hồi từ bộ phận đội xe. Giả định số va chạm giảm bằng một nửa số sự kiện. |

**20.000 × 3% × 10% × 33% ≈ 20 va chạm có thương tích tránh được mỗi năm** (khoảng 3 đến 116 tuỳ giả định).
Tham số chưa chắc chắn nhất là tỉ lệ va chạm. Dữ liệu GSM đang có sẽ thay được giả định này ngay.

**Đường mở rộng:**
1. Thử 100 xe chạy ca đêm trong 1 tháng. Đo số cảnh báo mỗi giờ lái, tỉ lệ báo động giả (tài xế bấm "tôi tỉnh"), và phản hồi của tài xế.
2. Đổi sang camera hồng ngoại để bỏ ca lỗi kính râm và ban đêm. Phần logic (hình học, thời gian, bất định) giữ nguyên.
3. Thêm dashboard cho bộ phận an toàn đội xe. Nghiên cứu Monash cho thấy phản hồi từ đội xe đưa mức giảm từ 66% lên 95%.
4. Mở rộng sang VinBus (tài xế xe buýt) và làm lớp logic cho DMS trên xe VinFast bán ở EU.

**Rủi ro khi đưa vào thực tế:**
- **Báo động giả quá nhiều** khiến tài xế lờ cảnh báo đi hoặc dán băng che camera. Vì vậy chỉ số báo động giả mỗi phút quan trọng ngang recall.
- **Quyền riêng tư:** video mặt tài xế phải được xử lý ngay trên thiết bị, chỉ gửi sự kiện (thời điểm, loại cảnh báo), không gửi hình.
- **Ca im lặng** như kính râm: tài xế có thể tin hệ thống trong khi nó không thấy gì.
- **Trách nhiệm pháp lý** khi hệ thống bỏ sót một lần vi giấc ngủ.

## 8. Dữ liệu an toàn

Chỉ dùng khuôn mặt của chính tác giả. Không dùng dữ liệu bệnh nhân, sinh viên hay tài xế thật. `logs/` và `recordings/` nằm trong `.gitignore` nên **không đẩy video mặt người lên repo công khai**. Repo chỉ chứa các số đo tổng hợp trong `reports/`.

## 9. Cấu trúc repo

```
app.py                     demo trực tiếp / replay video
dms/                       config, features, head_pose, kalman, quality, state, pipeline, hud, io_utils
scripts/                   live_check, record_protocol, protocols, evaluate, plot_session, bench_headpose, calibrate_camera
tests/test_core.py         22 test: solvePnP, quy ước dấu, góc mắt, Kalman với dt thay đổi, máy trạng thái, độc lập FPS,
                           PERCLOS, hysteresis, hợp nhất EAR + blendshape
reports/                   số đo đã chạy (headpose_bench, live_check, kết quả evaluate; v1_* = hệ thống v1)
docs/PRESENTATION.md       kịch bản 10 phút và chuẩn bị hỏi đáp
models/face_landmarker.task
```

## Nguồn

- AAA Foundation for Traffic Safety, *Drowsy Driving in Fatal Crashes, 2017–2021*: https://aaafoundation.org/?p=1121 . Báo cáo năm 2014: https://newsroom.aaa.com/wp-content/uploads/2019/06/AAAFoundation-DrowsyDriving-Nov2014.pdf
- ADDW bắt buộc tại EU từ 7/7/2026: https://smarteye.se/news/advanced-driver-distraction-warning-systems-now-mandatory-across-all-new-eu-vehicles/ , https://www.traffictechnologytoday.com/news/enforcement/eu-mandates-driver-distraction-warning-tech-in-cars.html
- Hiệu quả cảnh báo trong cabin (Seeing Machines, Monash University Accident Research Centre): https://www.ttnews.com/articles/seeing-machines-releases-safety-results-fatigue-distraction-monitoring-system , https://www.ccjdigital.com/fleet-testing-shows-reduced-drowsydistracted-driving-with-guardian-driver-safety-solution
- Quy mô đội xe GSM: https://jobsgo.vn/tuyen-dung/cong-ty-co-phan-di-chuyen-xanh-va-thong-minh-gsm-1557456984.html . Thị phần Xanh SM: https://mekongasean.vn/vuot-qua-grab-xanh-sm-tiep-tuc-dan-dau-thi-truong-taxi-viet-nam-quy-22025-44250.html
- Soukupová & Čech (2016), *Real-Time Eye Blink Detection using Facial Landmarks* (EAR).
- MediaPipe Face Landmarker: https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker
