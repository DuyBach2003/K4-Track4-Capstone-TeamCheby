"""HÌNH HỌC: ước lượng góc đầu 3D bằng cv2.solvePnP và khoảng cách tới camera bằng mô hình pinhole.

Hệ toạ độ mô hình mặt theo quy ước camera OpenCV: x sang phải ảnh, y xuống dưới, z hướng ra xa camera.
Mặt nhìn thẳng vào camera -> R ~ I -> yaw = pitch = roll = 0.
Góc Euler theo thứ tự R = Rz(roll) @ Ry(yaw) @ Rx(pitch).
Dấu: yaw > 0 khi mặt hướng về phía trái ảnh; pitch < 0 khi cúi xuống. Logic cảnh báo chỉ dùng |yaw|.
"""
import math

import cv2
import numpy as np


# 13 điểm CỨNG (rigid) lấy từ canonical_face_model.obj của MediaPipe (đơn vị cm), đã đổi sang hệ OpenCV
# (y_cv = -y, z_cv = -z). Cố ý bỏ cằm, miệng, mí mắt: các điểm này di chuyển khi ngáp/nhắm mắt
# và sẽ làm solvePnP tưởng là đầu đang gật. Vì mô hình có đơn vị cm nên tvec cho luôn khoảng cách (cm).
CANONICAL_RIGID = {
    1: (0.0, -1.126865, 7.475604),      # đỉnh mũi
    4: (0.0, -0.463170, 7.586580),
    6: (0.0, 2.473255, 5.788627),       # sống mũi
    168: (0.0, 3.271027, 5.236015),     # giữa 2 mắt
    9: (0.0, 4.885979, 5.385258),
    151: (0.0, 6.545390, 5.027311),
    10: (0.0, 8.261778, 4.481535),      # đỉnh trán
    33: (-4.445859, 2.663991, 3.173422),   # khoé mắt ngoài (bên trái ảnh)
    133: (-1.856432, 2.585245, 3.757904),  # khoé mắt trong
    362: (1.856432, 2.585245, 3.757904),
    263: (4.445859, 2.663991, 3.173422),   # khoé mắt ngoài (bên phải ảnh)
    234: (-7.664182, 0.673132, -2.435867),  # mép mặt (gần tai)
    454: (7.664182, 0.673132, -2.435867),
}
IMAGE_IDS = list(CANONICAL_RIGID)
MODEL_POINTS = np.array([[x, -y, -z] for x, y, z in CANONICAL_RIGID.values()], dtype=np.float64)
MODEL_POINTS -= MODEL_POINTS[0]   # gốc toạ độ tại đỉnh mũi


def camera_matrix(width: int, height: int, focal_scale: float = 0.85) -> np.ndarray:
    """Xấp xỉ nội tham số khi chưa hiệu chuẩn: f = focal_scale * W, tâm ảnh ở giữa, không méo."""
    f = focal_scale * width
    return np.array([[f, 0, width / 2.0], [0, f, height / 2.0], [0, 0, 1]], dtype=np.float64)


def euler_to_matrix(yaw: float, pitch: float, roll: float) -> np.ndarray:
    y, p, r = map(math.radians, (yaw, pitch, roll))
    rx = np.array([[1, 0, 0], [0, math.cos(p), -math.sin(p)], [0, math.sin(p), math.cos(p)]])
    ry = np.array([[math.cos(y), 0, math.sin(y)], [0, 1, 0], [-math.sin(y), 0, math.cos(y)]])
    rz = np.array([[math.cos(r), -math.sin(r), 0], [math.sin(r), math.cos(r), 0], [0, 0, 1]])
    return rz @ ry @ rx


def matrix_to_euler(rot: np.ndarray):
    """Nghịch đảo của euler_to_matrix. Trả về (yaw, pitch, roll) độ."""
    yaw = math.degrees(math.asin(max(-1.0, min(1.0, -rot[2, 0]))))
    pitch = math.degrees(math.atan2(rot[2, 1], rot[2, 2]))
    roll = math.degrees(math.atan2(rot[1, 0], rot[0, 0]))
    # Quy ước dấu cho người dùng: cúi xuống = pitch âm (trục y ảnh hướng xuống nên đảo dấu)
    return yaw, -pitch, roll


def estimate_head_pose(px: np.ndarray, cam: np.ndarray):
    """px: mốc pixel (N, 2) của 478 mốc. Trả về (yaw, pitch, roll, rvec, tvec) hoặc None."""
    image_points = px[IMAGE_IDS].astype(np.float64)
    ok, rvec, tvec = cv2.solvePnP(MODEL_POINTS, image_points, cam, None, flags=cv2.SOLVEPNP_ITERATIVE)
    if not ok:
        return None
    rot, _ = cv2.Rodrigues(rvec)
    yaw, pitch, roll = matrix_to_euler(rot)
    return yaw, pitch, roll, rvec, tvec


def distance_cm(tvec) -> float:
    """Khoảng cách camera -> đỉnh mũi (cm). Đúng tới mức K xấp xỉ đúng: sai f 10% => sai khoảng cách 10%."""
    return float(np.linalg.norm(tvec))


def project_model(yaw, pitch, roll, cam, distance_cm=60.0):
    """Dùng cho kiểm thử: chiếu mô hình mặt với góc đã biết ra ảnh."""
    rot = euler_to_matrix(yaw, -pitch, roll)
    rvec, _ = cv2.Rodrigues(rot)
    tvec = np.array([[0.0], [0.0], [distance_cm]])
    pts, _ = cv2.projectPoints(MODEL_POINTS, rvec, tvec, cam, None)
    return pts.reshape(-1, 2)


def draw_axes(frame, rvec, tvec, cam, nose_px, length=8.0):
    axes = np.float64([[length, 0, 0], [0, length, 0], [0, 0, -length]])
    pts, _ = cv2.projectPoints(axes, rvec, tvec, cam, None)
    o = tuple(int(v) for v in nose_px)
    for p, color in zip(pts.reshape(-1, 2), [(0, 0, 255), (0, 255, 0), (255, 0, 0)]):
        cv2.line(frame, o, (int(p[0]), int(p[1])), color, 2)
