"""BẤT ĐỊNH: đo chất lượng đầu vào để biết khi nào KHÔNG nên tin đầu ra.

Nguyên tắc: hệ thống an toàn phải "fail loud". Khi không chắc thì hiện KHONG CHAC CHAN kèm lý do,
không được im lặng báo "tỉnh táo".
"""
import cv2
import numpy as np


def roi_quality(gray: np.ndarray, bbox) -> tuple[float, float]:
    """Trả về (độ sáng trung bình, độ nét = phương sai Laplacian) của vùng mặt."""
    x0, y0, x1, y1 = bbox
    roi = gray[y0:y1, x0:x1]
    if roi.size == 0:
        roi = gray
    # Đưa về kích thước cố định để độ nét không phụ thuộc mặt to/nhỏ trong ảnh
    roi = cv2.resize(roi, (128, 128), interpolation=cv2.INTER_AREA)
    return float(roi.mean()), float(cv2.Laplacian(roi, cv2.CV_64F).var())


def uncertainty_reasons(cfg, face_found: bool, brightness: float, sharpness: float, yaw: float,
                        face_lost_s: float) -> list[str]:
    reasons = []
    if not face_found:
        if face_lost_s >= cfg.face_lost_grace_s:
            reasons.append("NO_FACE")
        return reasons
    if brightness < cfg.min_brightness:
        reasons.append("LOW_LIGHT")
    if sharpness < cfg.min_sharpness:
        reasons.append("BLUR")
    if abs(yaw) > cfg.max_reliable_yaw:
        reasons.append("EXTREME_YAW")
    return reasons
