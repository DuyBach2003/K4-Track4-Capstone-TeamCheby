"""BIỂU DIỄN: từ 478 mốc khuôn mặt rút ra vài con số có ý nghĩa (EAR, MAR).

Lưu ý: mốc MediaPipe được chuẩn hoá theo (rộng, cao) ảnh. Phải đổi về pixel trước khi đo
khoảng cách, nếu không ảnh 16:9 sẽ làm méo tỉ lệ dọc/ngang và EAR bị sai lệch có hệ thống.
"""
import numpy as np

# 6 điểm mỗi mắt theo thứ tự p1..p6 của công thức EAR (Soukupová & Čech, 2016)
RIGHT_EYE = [33, 160, 158, 133, 153, 144]   # mắt phải của tài xế (bên trái ảnh)
LEFT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH = [78, 308, 13, 14]                    # khoé trái, khoé phải, môi trên trong, môi dưới trong
# Tâm mống mắt (chỉ có ở model 478 mốc) và 2 khoé của cùng mắt đó, theo thứ tự trái -> phải trên ảnh
RIGHT_IRIS, RIGHT_CORNERS = 468, (33, 133)
LEFT_IRIS, LEFT_CORNERS = 473, (362, 263)

# Mô hình nhãn cầu: khe mắt (khoé - khoé) ~ 30 mm, bán kính nhãn cầu ~ 12 mm.
# Mống mắt lệch d mm khỏi giữa khe mắt <=> mắt xoay asin(d / 12) => sin = (lệch / bề rộng khe) * 30/12.
EYE_WIDTH_OVER_RADIUS = 30.0 / 12.0


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


def eye_in_head_yaw(px: np.ndarray, iris: int, corners) -> float:
    """HÌNH HỌC: góc mắt xoay ngang trong hốc mắt (độ), cùng quy ước dấu với yaw của đầu.

    Lý do cần: khi nhìn sang bên, người ta chỉ quay đầu một phần, phần còn lại là mắt. Ngược lại, người quay đầu
    nhưng mắt vẫn nhìn đường thì không xao nhãng. Dữ liệu thật (reports/v1_*) cho thấy cả hai trường hợp.
    Tỉ số lệch/bề rộng khe mắt không đổi khi mặt xa/gần hay bị co ngắn do quay đầu (cả hai cùng co).
    """
    a, b = px[corners[0]], px[corners[1]]
    width = np.linalg.norm(b - a)
    if width < 1e-6:
        return 0.0
    offset = float((px[iris] - (a + b) / 2) @ (b - a)) / width ** 2
    # Mống mắt lệch sang PHẢI ảnh = mắt xoay về phía TRÁI của tài xế = yaw âm (yaw > 0 là mặt hướng về trái ảnh)
    return -float(np.degrees(np.arcsin(np.clip(offset * EYE_WIDTH_OVER_RADIUS, -1.0, 1.0))))


def face_features(px: np.ndarray) -> dict:
    ear_r = eye_aspect_ratio(px[RIGHT_EYE])
    ear_l = eye_aspect_ratio(px[LEFT_EYE])
    return {
        "ear_r": ear_r,
        "ear_l": ear_l,
        "mar": mouth_aspect_ratio(px[MOUTH]),
        "eye_yaw_r": eye_in_head_yaw(px, RIGHT_IRIS, RIGHT_CORNERS),
        "eye_yaw_l": eye_in_head_yaw(px, LEFT_IRIS, LEFT_CORNERS),
    }


def face_bbox(px: np.ndarray, width: int, height: int, pad: float = 0.1):
    x0, y0 = px.min(axis=0)
    x1, y1 = px.max(axis=0)
    dx, dy = (x1 - x0) * pad, (y1 - y0) * pad
    x0, y0 = max(0, int(x0 - dx)), max(0, int(y0 - dy))
    x1, y1 = min(width, int(x1 + dx)), min(height, int(y1 + dy))
    return x0, y0, x1, y1
