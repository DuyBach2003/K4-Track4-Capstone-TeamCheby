"""BIỂU DIỄN: từ 478 mốc khuôn mặt rút ra vài con số có ý nghĩa (EAR, MAR).

Lưu ý: mốc MediaPipe được chuẩn hoá theo (rộng, cao) ảnh. Phải đổi về pixel trước khi đo
khoảng cách, nếu không ảnh 16:9 sẽ làm méo tỉ lệ dọc/ngang và EAR bị sai lệch có hệ thống.
"""
import numpy as np

# 6 điểm mỗi mắt theo thứ tự p1..p6 của công thức EAR (Soukupová & Čech, 2016)
RIGHT_EYE = [33, 160, 158, 133, 153, 144]   # mắt phải của tài xế (bên trái ảnh)
LEFT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [78, 308, 13, 14]                    # khoé trái, khoé phải, môi trên trong, môi dưới trong


def to_pixels(landmarks, width: int, height: int) -> np.ndarray:
    """Danh sách mốc chuẩn hoá -> mảng (N, 2) toạ độ pixel."""
    return np.array([[lm.x * width, lm.y * height] for lm in landmarks], dtype=np.float64)


def eye_aspect_ratio(pts: np.ndarray) -> float:
    """pts: (6, 2) theo thứ tự p1..p6. EAR = (|p2-p6| + |p3-p5|) / (2 |p1-p4|)."""
    p1, p2, p3, p4, p5, p6 = pts
    horizontal = np.linalg.norm(p1 - p4)
    if horizontal < 1e-6:
        return 0.0
    return float((np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * horizontal))


def mouth_aspect_ratio(pts: np.ndarray) -> float:
    """pts: (4, 2) = khoé trái, khoé phải, môi trên, môi dưới."""
    left, right, top, bottom = pts
    width = np.linalg.norm(left - right)
    if width < 1e-6:
        return 0.0
    return float(np.linalg.norm(top - bottom) / width)


def face_features(px: np.ndarray) -> dict:
    ear_r = eye_aspect_ratio(px[RIGHT_EYE])
    ear_l = eye_aspect_ratio(px[LEFT_EYE])
    return {
        "ear_r": ear_r,
        "ear_l": ear_l,
        "mar": mouth_aspect_ratio(px[MOUTH]),
    }


def face_bbox(px: np.ndarray, width: int, height: int, pad: float = 0.1):
    x0, y0 = px.min(axis=0)
    x1, y1 = px.max(axis=0)
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad
    x0, y0 = max(0, int(x0 - dx)), max(0, int(y0 - dy))
    x1, y1 = min(width, int(x1 + dx)), min(height, int(y1 + dy))
    return x0, y0, x1, y1
