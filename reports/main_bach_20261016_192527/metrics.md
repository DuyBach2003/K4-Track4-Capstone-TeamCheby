# Kết quả đánh giá: `main_bach_20261016_192527.mp4`

- 2681 frame, 89.8 s, FPS ghi thực tế 29.7, thấy mặt 100.0% frame, hiệu chuẩn xong lúc 3.4 s

## 1. Mắt nhắm/mở theo frame

Bỏ 0.7 s đầu mỗi đoạn (thời gian phản ứng), bỏ đoạn chớp mắt tự do/ngáp/quay đầu.

| Phương pháp | Precision | Recall | F1 | Accuracy | n frame |
|---|---|---|---|---|---|
| Hệ thống: EAR cá nhân hoá VÀ blendshape (cả 2 mắt) | 0.76 | 0.72 | 0.74 | 0.91 | 1472 |
| Chỉ blendshape eyeBlink > 0.5 (MediaPipe) | 0.82 | 0.72 | 0.77 | 0.92 | 1472 |

## 2. Theo sự kiện (cảnh báo có kịp không)

| Đoạn | Mong đợi | Bắt được | Trễ từ lúc có lời nhắc (s) |
|---|---|---|---|
| NHAM MAT 4 giay | DROWSY | ✅ | 2.49 |
| NHAM MAT 3 giay | DROWSY | ✅ | 3.32 |
| QUAY DAU SANG TRAI (nhin cua so) | DISTRACTED | ❌ | – |
| QUAY DAU SANG PHAI | DISTRACTED | ❌ | – |
| CUI XUONG nhin dien thoai | DISTRACTED | ❌ | – |
| NHAM MAT 4 giay | DROWSY | ✅ | 1.80 |

- Tỉ lệ bắt sự kiện: **50%**; trễ TB buồn ngủ **2.54 s** (gồm ngưỡng 1.0 s + phản ứng người), xao nhãng **– s** (ngưỡng 2.0 s)
- Báo động giả: **0** lần trong 44 s bình thường = 0.00 lần/phút

## 3. Thời gian và độ ổn định

- Độ trễ xử lý frame→quyết định: p50 **3.9 ms**, p95 4.1 ms (riêng model p50 2.9 ms)
- Độ rung góc đầu giữa 2 frame liên tiếp khi ngồi yên (std của chênh lệch): yaw thô 0.51° → Kalman 0.53°; pitch thô 0.28° → Kalman 0.24°

## 4. Từng đoạn (dùng để tìm ca lỗi)

| t (s) | Lời nhắc | Mong đợi | Trạng thái chính | Báo động | Thấy mặt % | EAR TB | % nhắm | \|nhìn ngang\| | pitch đầu | % không chắc | Đạt |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 0 | Nhin thang, mo mat binh thuong (hieu chuan) | ANY | CALIBRATING | - | 100 | 0.25 | 0 | 3 | +3 | 0 | – |
| 6 | Nhin thang, CHOP MAT tu nhien | OK | OK | - | 100 | 0.22 | 6 | 6 | +2 | 0 | ✅ |
| 16 | NHAM MAT 4 giay | DROWSY | OK | DROWSY | 100 | 0.09 | 77 | 7 | +0 | 0 | ✅ |
| 20 | Mo mat, nhin thang | OK | FATIGUE | DROWSY | 100 | 0.25 | 6 | 8 | -0 | 0 | ❌ |
| 26 | NHAM MAT 3 giay | DROWSY | FATIGUE | - | 100 | 0.20 | 30 | 8 | +0 | 0 | ❌ |
| 29 | Mo mat, nhin thang | OK | FATIGUE | DROWSY | 100 | 0.23 | 9 | 6 | +0 | 0 | ❌ |
| 35 | QUAY DAU SANG TRAI (nhin cua so) | DISTRACTED | FATIGUE | - | 100 | 0.24 | 3 | 3 | +1 | 0 | ❌ |
| 40 | Nhin thang | OK | FATIGUE | - | 100 | 0.23 | 3 | 7 | +2 | 0 | ✅ |
| 45 | QUAY DAU SANG PHAI | DISTRACTED | FATIGUE | - | 100 | 0.24 | 0 | 17 | +3 | 0 | ❌ |
| 50 | Nhin thang | OK | OK | - | 100 | 0.25 | 2 | 9 | -0 | 0 | ✅ |
| 55 | CUI XUONG nhin dien thoai | DISTRACTED | OK | - | 100 | 0.19 | 6 | 9 | -14 | 0 | ❌ |
| 60 | Nhin thang | OK | OK | - | 100 | 0.24 | 1 | 8 | -0 | 0 | ✅ |
| 65 | NGAP 1 cai that to | ANY | OK | - | 100 | 0.27 | 0 | 16 | -3 | 0 | – |
| 69 | Nhin thang | OK | OK | - | 100 | 0.24 | 5 | 7 | -3 | 0 | ✅ |
| 74 | Nham mat NHANH roi mo (0.8s) | OK | OK | - | 100 | 0.26 | 0 | 1 | +2 | 0 | ✅ |
| 75 | Mo mat, nhin thang | OK | OK | - | 100 | 0.23 | 14 | 8 | +1 | 0 | ✅ |
| 81 | NHAM MAT 4 giay | DROWSY | DROWSY | DROWSY | 100 | 0.04 | 99 | 9 | -1 | 0 | ✅ |
| 85 | Mo mat - ket thuc | OK | FATIGUE | - | 100 | 0.27 | 0 | 7 | -1 | 0 | ✅ |

![timeline](timeline.png)
