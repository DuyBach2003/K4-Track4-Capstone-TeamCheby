"""Tham số của hệ thống. Mỗi ngưỡng có ghi lý do chọn để cả team giải thích được khi hỏi đáp."""
from dataclasses import dataclass


@dataclass
class DMSConfig:
    # ---------- HỌC (model) ----------
    model_path: str = "models/face_landmarker.task"
    min_face_detection_confidence: float = 0.5
    min_face_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5

    # ---------- HIỆU CHUẨN THEO TỪNG TÀI XẾ ----------
    # EAR lúc mở mắt khác nhau giữa người (mắt một mí ~0.22, mắt to ~0.33),
    # nên không dùng ngưỡng cố định 0.21 như bài báo Soukupová 2016 mà đo baseline 3 s đầu.
    calib_seconds: float = 3.0
    calib_max_abs_yaw: float = 20.0      # chỉ lấy mẫu khi đang nhìn thẳng
    closed_ratio: float = 0.65           # nhắm khi EAR < 0.65 * EAR_mở
    reopen_ratio: float = 0.75           # hysteresis: mở lại khi EAR > 0.75 * EAR_mở
    fallback_open_ear: float = 0.28      # dùng nếu không hiệu chuẩn được

    # ---------- THỜI GIAN (tính theo giây, không theo số frame vì FPS dao động) ----------
    blink_max_s: float = 0.5             # chớp mắt bình thường 0.1-0.4 s
    drowsy_alarm_s: float = 1.0          # nhắm liên tục >= 1 s = vi giấc ngủ (microsleep)
    perclos_window_s: float = 30.0       # chuẩn PERCLOS là 60 s, rút ngắn để demo được trong 10 phút
    perclos_warn: float = 0.15           # > 15% thời gian nhắm mắt = mệt mỏi
    perclos_min_history_s: float = 15.0  # cần ít nhất 15 s dữ liệu mới kết luận, nếu không vài cái chớp mắt đã > 15%
    distract_yaw_deg: float = 30.0       # quay đầu > 30 độ = không nhìn đường
    distract_pitch_down_deg: float = -20.0  # cúi > 20 độ = nhìn điện thoại / bảng táp-lô
    distract_alarm_s: float = 2.0        # Euro NCAP coi >= 3 s là xao nhãng dài; demo dùng 2 s
    yawn_mar: float = 0.55
    yawn_min_s: float = 1.2
    yawn_window_s: float = 120.0
    yawn_warn_count: int = 2

    # ---------- BẤT ĐỊNH ----------
    min_brightness: float = 45.0         # độ sáng trung bình vùng mặt (0-255) thấp hơn -> nghi ngờ
    min_sharpness: float = 15.0          # phương sai Laplacian vùng mặt thấp hơn -> mờ/rung
    max_reliable_yaw: float = 40.0       # quay quá 40 độ thì một mắt bị che, EAR không còn tin được
    face_lost_grace_s: float = 0.5       # mất mặt ngắn hơn 0.5 s: Kalman dự đoán tiếp

    # ---------- HÌNH HỌC ----------
    # Không có thông số hiệu chuẩn thật của webcam -> xấp xỉ f = hệ số * chiều rộng ảnh.
    # Webcam laptop có FOV ngang ~ 60-70 độ => f ~ 0.7-0.9 W. Sai số f ảnh hưởng ra sao: xem scripts/bench_headpose.py
    focal_scale: float = 0.85
    camera_matrix_path: str = ""          # nếu có file .npz từ calibrate_camera.py thì dùng

    # ---------- KALMAN cho góc đầu ----------
    kf_process_noise: float = 400.0      # (độ/s^2)^2: đầu người quay nhanh được tới ~ vài trăm độ/s
    # (độ)^2. Giả định ban đầu jitter 1-3 độ; đo thật (scripts/live_check.py) chỉ ~0.2 độ/frame vì MediaPipe VIDEO
    # mode đã tự làm mượt mốc. Giữ R lớn hơn thực tế một chút: Kalman ở đây chủ yếu để dự đoán khi mất mặt ngắn
    # và cho độ bất định pose_std, không phải để làm mượt.
    kf_measurement_noise: float = 4.0

    # ---------- CẢNH BÁO ----------
    sound: bool = True
    sound_cooldown_s: float = 1.5
