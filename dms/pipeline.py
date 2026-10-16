"""Ghép toàn bộ hệ thống: ảnh -> mốc mặt -> đặc trưng + góc đầu -> lọc thời gian -> trạng thái.

    camera frame (t)
        |  HỌC: MediaPipe FaceLandmarker (pretrained, 478 mốc 3D + 52 blendshape)
        v
    478 mốc (pixel)  --BIỂU DIỄN-->  EAR trái/phải, MAR
        |  HÌNH HỌC: solvePnP 6 điểm + K xấp xỉ  -> yaw/pitch/roll, khoảng cách (cm)
        v
    THỜI GIAN: Kalman (góc đầu, dt thật) ; BẤT ĐỊNH: độ sáng, độ nét, |yaw| lớn, mất mặt
        v
    TemporalStateMachine -> OK / FATIGUE / DROWSY / DISTRACTED / UNCERTAIN
        v
    DỮ LIỆU: log CSV từng frame (kèm latency) để replay và đánh giá
"""
import time

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from . import features as F
from .head_pose import camera_matrix, distance_cm, estimate_head_pose
from .kalman import ConstantVelocityKF
from .quality import roi_quality, uncertainty_reasons
from .state import TemporalStateMachine

LOG_FIELDS = [
    "t", "frame", "face", "ear_l", "ear_r", "ear", "blink_bs", "mar",
    "yaw_raw", "pitch_raw", "roll_raw", "yaw", "pitch", "roll", "yaw_rel", "pitch_rel", "pose_std",
    "dist_cm", "brightness", "sharpness", "eyes_closed", "closed_s", "away_s",
    "perclos", "yawns", "blinks", "open_ear", "closed_thr", "state", "reasons",
    "infer_ms", "latency_ms",
]


class DMSPipeline:
    def __init__(self, cfg):
        self.cfg = cfg
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=cfg.model_path),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=cfg.min_face_detection_confidence,
            min_face_presence_confidence=cfg.min_face_presence_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
            output_face_blendshapes=True,
        )
        self.landmarker = vision.FaceLandmarker.create_from_options(options)
        self.kf = {k: ConstantVelocityKF(cfg.kf_process_noise, cfg.kf_measurement_noise)
                   for k in ("yaw", "pitch", "roll")}
        self.sm = TemporalStateMachine(cfg)
        self.cam = None
        self.frame_idx = 0
        self.last_t = None
        self.last_ts_ms = -1
        self.face_lost_since = None

    def _camera(self, w, h):
        if self.cam is None:
            if self.cfg.camera_matrix_path:
                self.cam = np.load(self.cfg.camera_matrix_path)["K"]
            else:
                self.cam = camera_matrix(w, h, self.cfg.focal_scale)
        return self.cam

    def recalibrate(self):
        self.sm.reset()

    def process(self, frame_bgr: np.ndarray, t: float, t_capture: float | None = None) -> dict:
        """t: thời điểm của frame (giây, đơn điệu tăng). t_capture: perf_counter() lúc đọc frame, để đo độ trễ."""
        t_capture = t_capture if t_capture is not None else time.perf_counter()
        h, w = frame_bgr.shape[:2]
        cam = self._camera(w, h)
        dt = 0.0 if self.last_t is None else max(1e-3, t - self.last_t)
        self.last_t = t

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        ts_ms = max(int(t * 1000), self.last_ts_ms + 1)   # MediaPipe VIDEO mode cần timestamp tăng ngặt
        self.last_ts_ms = ts_ms
        t0 = time.perf_counter()
        res = self.landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts_ms)
        infer_ms = (time.perf_counter() - t0) * 1000

        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        r = {k: float("nan") for k in LOG_FIELDS}
        r.update(t=t, frame=self.frame_idx, face=0, px=None, rvec=None, tvec=None)
        self.frame_idx += 1

        face = None
        if res.face_landmarks:
            px = F.to_pixels(res.face_landmarks[0], w, h)
            feats = F.face_features(px)
            bbox = F.face_bbox(px, w, h)
            brightness, sharpness = roi_quality(gray, bbox)
            pose = estimate_head_pose(px, cam)
            bs = {c.category_name: c.score for c in res.face_blendshapes[0]} if res.face_blendshapes else {}
            r.update(face=1, px=px, bbox=bbox, brightness=brightness, sharpness=sharpness,
                     ear_l=feats["ear_l"], ear_r=feats["ear_r"], mar=feats["mar"],
                     blink_bs=(bs.get("eyeBlinkLeft", np.nan) + bs.get("eyeBlinkRight", np.nan)) / 2)
            if pose is not None:
                yaw, pitch, roll, rvec, tvec = pose
                r.update(yaw_raw=yaw, pitch_raw=pitch, roll_raw=roll, rvec=rvec, tvec=tvec)
                r["yaw"] = self.kf["yaw"].update(yaw, dt)
                r["pitch"] = self.kf["pitch"].update(pitch, dt)
                r["roll"] = self.kf["roll"].update(roll, dt)
                r["dist_cm"] = distance_cm(tvec)
            # Khi quay đầu, mắt xa camera bị co ngắn và che khuất -> chỉ tin mắt gần camera hơn
            yaw_now = r["yaw"] if not np.isnan(r["yaw"]) else 0.0
            if abs(yaw_now) > 20:
                r["ear"] = feats["ear_l"] if yaw_now > 0 else feats["ear_r"]
            else:
                r["ear"] = (feats["ear_l"] + feats["ear_r"]) / 2
            face = {"ear": r["ear"], "mar": r["mar"], "yaw": yaw_now,
                    "pitch": r["pitch"] if not np.isnan(r["pitch"]) else 0.0}
            self.face_lost_since = None
        else:
            if self.face_lost_since is None:
                self.face_lost_since = t
            # Mất mặt ngắn: Kalman dự đoán tiếp để HUD không nhảy; độ bất định pose_std tăng dần
            if t - self.face_lost_since < self.cfg.face_lost_grace_s:
                for k in ("yaw", "pitch", "roll"):
                    r[k] = self.kf[k].predict(dt)
            else:
                for kf in self.kf.values():
                    kf.reset()
            r["brightness"], r["sharpness"] = roi_quality(gray, (0, 0, w, h))

        face_lost_s = 0.0 if self.face_lost_since is None else t - self.face_lost_since
        reasons = uncertainty_reasons(self.cfg, face is not None, r["brightness"], r["sharpness"],
                                      face["yaw"] if face else 0.0, face_lost_s)
        st = self.sm.update(t, face, reasons)
        r.update(yaw_rel=st.yaw_rel, pitch_rel=st.pitch_rel, eyes_closed=int(st.eyes_closed), closed_s=st.closed_s, away_s=st.away_s, perclos=st.perclos,
                 yawns=st.yawns_recent, blinks=st.blinks, open_ear=st.open_ear, closed_thr=st.closed_thr,
                 state=st.state, reasons="|".join(st.reasons), calib_progress=st.calib_progress,
                 pose_std=self.kf["yaw"].std if self.kf["yaw"].initialized else float("nan"),
                 infer_ms=infer_ms)
        r["latency_ms"] = (time.perf_counter() - t_capture) * 1000
        return r

    def close(self):
        self.landmarker.close()
