"""THỜI GIAN + BIỂU DIỄN: biến chuỗi số đo theo từng frame thành trạng thái tài xế.

Mọi bộ đếm tính bằng giây từ timestamp thật, không đếm frame: cùng một ngưỡng "nhắm 1 s" phải đúng
dù webcam chạy 15 FPS (máy yếu, thiếu sáng) hay 30 FPS.
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np

# Thứ tự ưu tiên khi hiển thị (cao -> thấp)
CALIBRATING = "CALIBRATING"
UNCERTAIN = "UNCERTAIN"
DROWSY = "DROWSY"
DISTRACTED = "DISTRACTED"
FATIGUE = "FATIGUE"
OK = "OK"

ALARM_STATES = {DROWSY, DISTRACTED}


@dataclass
class DriverState:
    state: str = CALIBRATING
    reasons: list = field(default_factory=list)
    eyes_closed: bool = False
    closed_s: float = 0.0
    away_s: float = 0.0
    perclos: float = 0.0
    yawns_recent: int = 0
    blinks: int = 0
    open_ear: float = float("nan")
    closed_thr: float = float("nan")
    calib_progress: float = 0.0
    yaw_rel: float = float("nan")
    pitch_rel: float = float("nan")


class TemporalStateMachine:
    def __init__(self, cfg):
        self.cfg = cfg
        self.reset()

    def reset(self):
        self.calib_samples = []
        self.pose_samples = []
        self.neutral = (0.0, 0.0)
        self.calib_time = 0.0
        self.open_ear = None
        self.eyes_closed = False
        self.closed_since = None
        self.away_since = None
        self.yawn_since = None
        self.yawn_times = deque()
        self.blinks = 0
        self.last_t = None
        self.no_face_since = None
        # (t, dt, closed) cho PERCLOS có trọng số thời gian
        self.history = deque()

    def thresholds(self):
        base = self.open_ear if self.open_ear else self.cfg.fallback_open_ear
        return base, base * self.cfg.closed_ratio, base * self.cfg.reopen_ratio

    def update(self, t: float, face: dict | None, reasons: list) -> DriverState:
        cfg = self.cfg
        dt = 0.0 if self.last_t is None else max(0.0, t - self.last_t)
        self.last_t = t
        out = DriverState(blinks=self.blinks)

        if face is None:
            self.no_face_since = self.no_face_since if self.no_face_since is not None else t
        else:
            self.no_face_since = None

        # Khi đầu vào không tin được: không cập nhật bộ đếm mắt (tránh báo động giả vì ngược sáng),
        # nhưng vẫn báo UNCERTAIN để người dùng biết hệ thống đang "mù".
        eye_reliable = face is not None and not ({"LOW_LIGHT", "BLUR", "EXTREME_YAW"} & set(reasons))

        # ----- Hiệu chuẩn baseline EAR -----
        if self.open_ear is None:
            if face is not None and eye_reliable and abs(face["yaw"]) < cfg.calib_max_abs_yaw:
                self.calib_samples.append(face["ear"])
                self.pose_samples.append((face["yaw"], face["pitch"]))
                self.calib_time += dt
            out.calib_progress = min(1.0, self.calib_time / cfg.calib_seconds)
            if self.calib_time >= cfg.calib_seconds and len(self.calib_samples) >= 10:
                # Phân vị 70: bỏ qua các frame đang chớp mắt trong lúc hiệu chuẩn
                self.open_ear = float(np.percentile(self.calib_samples, 70))
                # Tư thế "nhìn đường" của riêng tài xế này. Camera DMS thật gắn ở cột lái/gương nên nhìn
                # tài xế từ dưới lên một góc; trừ đi góc này để "xao nhãng" là lệch so với lúc nhìn đường.
                self.neutral = tuple(np.median(np.array(self.pose_samples), axis=0))
            else:
                out.state = CALIBRATING
                out.reasons = list(reasons)
                return out

        base, close_thr, reopen_thr = self.thresholds()
        out.open_ear, out.closed_thr = base, close_thr

        # ----- Mắt -----
        if eye_reliable:
            ear = face["ear"]
            was_closed = self.eyes_closed
            if self.eyes_closed:
                self.eyes_closed = ear < reopen_thr
            else:
                self.eyes_closed = ear < close_thr
            if self.eyes_closed and not was_closed:
                self.closed_since = t
            if was_closed and not self.eyes_closed:
                if self.closed_since is not None and t - self.closed_since <= cfg.blink_max_s:
                    self.blinks += 1
                self.closed_since = None
            self.history.append((t, dt, self.eyes_closed))

        while self.history and self.history[0][0] < t - cfg.perclos_window_s:
            self.history.popleft()
        total = sum(h[1] for h in self.history)
        closed = sum(h[1] for h in self.history if h[2])
        out.perclos = closed / total if total > 1.0 else 0.0
        out.eyes_closed = self.eyes_closed
        out.closed_s = (t - self.closed_since) if (self.eyes_closed and self.closed_since is not None) else 0.0
        out.blinks = self.blinks

        # ----- Hướng nhìn -----
        if face is not None:
            out.yaw_rel = face["yaw"] - self.neutral[0]
            out.pitch_rel = face["pitch"] - self.neutral[1]
            away = abs(out.yaw_rel) > cfg.distract_yaw_deg or out.pitch_rel < cfg.distract_pitch_down_deg
            if away and self.away_since is None:
                self.away_since = t
            elif not away:
                self.away_since = None
        out.away_s = (t - self.away_since) if self.away_since is not None else 0.0

        # ----- Ngáp -----
        if face is not None and face["mar"] > cfg.yawn_mar:
            if self.yawn_since is None:
                self.yawn_since = t
        else:
            if self.yawn_since is not None and t - self.yawn_since >= cfg.yawn_min_s:
                self.yawn_times.append(t)
            self.yawn_since = None
        while self.yawn_times and self.yawn_times[0] < t - cfg.yawn_window_s:
            self.yawn_times.popleft()
        out.yawns_recent = len(self.yawn_times)

        # ----- Hợp nhất thành 1 trạng thái theo mức ưu tiên -----
        out.reasons = list(reasons)
        if out.closed_s >= cfg.drowsy_alarm_s:
            out.state = DROWSY
        elif out.away_s >= cfg.distract_alarm_s:
            out.state = DISTRACTED
        elif face is None and self.no_face_since is not None and t - self.no_face_since >= cfg.face_lost_grace_s:
            out.state = UNCERTAIN
        elif not eye_reliable and face is not None and "EXTREME_YAW" not in reasons:
            out.state = UNCERTAIN
        elif (out.perclos > cfg.perclos_warn and total >= cfg.perclos_min_history_s) \
                or out.yawns_recent >= cfg.yawn_warn_count:
            out.state = FATIGUE
        else:
            out.state = OK
        return out
