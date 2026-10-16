"""THỜI GIAN + BẤT ĐỊNH: Kalman filter vận tốc không đổi, viết bằng NumPy.

Trạng thái x = [góc, vận tốc góc]. dt lấy từ timestamp thật của từng frame (FPS webcam dao động 15-30),
nên ma trận F, Q được tính lại mỗi bước thay vì cố định cho 30 Hz.
Khi mất mặt ngắn hạn (che tay, ngược sáng 1-2 frame) chỉ chạy predict() để giữ đầu ra liên tục,
và phương sai P tăng dần -> biết lúc nào không còn nên tin.

Vì sao chỉ lọc góc đầu mà không lọc EAR: chớp mắt chỉ kéo dài 100-400 ms; làm mượt EAR sẽ
xoá mất chớp mắt và làm trễ cảnh báo. Góc đầu thì thay đổi chậm hơn nhiều so với nhiễu mốc.
"""
import numpy as np


class ConstantVelocityKF:
    def __init__(self, process_noise: float = 400.0, measurement_noise: float = 4.0):
        self.q = process_noise
        self.r = measurement_noise
        self.x = None
        self.P = None
        self.H = np.array([[1.0, 0.0]])

    @property
    def initialized(self) -> bool:
        return self.x is not None

    def _fq(self, dt: float):
        F = np.array([[1.0, dt], [0.0, 1.0]])
        # Nhiễu gia tốc trắng rời rạc (discrete white noise acceleration)
        Q = self.q * np.array([[dt ** 4 / 4, dt ** 3 / 2], [dt ** 3 / 2, dt ** 2]])
        return F, Q

    def predict(self, dt: float) -> float:
        if not self.initialized:
            return float("nan")
        F, Q = self._fq(max(dt, 1e-3))
        self.x = F @ self.x
        self.P = F @ self.P @ F.T + Q
        return float(self.x[0, 0])

    def update(self, z: float, dt: float) -> float:
        if not self.initialized:
            self.x = np.array([[z], [0.0]])
            self.P = np.diag([self.r, 100.0])
            return z
        self.predict(dt)
        y = z - (self.H @ self.x)[0, 0]
        S = (self.H @ self.P @ self.H.T)[0, 0] + self.r
        K = self.P @ self.H.T / S
        self.x = self.x + K * y
        self.P = (np.eye(2) - K @ self.H) @ self.P
        return float(self.x[0, 0])

    @property
    def std(self) -> float:
        return float(np.sqrt(self.P[0, 0])) if self.initialized else float("inf")

    def reset(self):
        self.x = None
        self.P = None
