"""Giao diện trên cửa sổ OpenCV. Chữ không dấu vì cv2.putText không hỗ trợ Unicode."""
from collections import deque

import cv2
import numpy as np

from . import features as F
from .head_pose import IMAGE_IDS, draw_axes

STATE_STYLE = {
    "CALIBRATING": ((200, 160, 0), "DANG HIEU CHUAN - nhin thang, mo mat binh thuong"),
    "OK": ((60, 170, 60), "TINH TAO"),
    "FATIGUE": ((0, 190, 255), "MET MOI - nen nghi ngoi"),
    "DROWSY": ((0, 0, 255), "BUON NGU! MO MAT RA"),
    "DISTRACTED": ((0, 90, 255), "MAT TAP TRUNG - NHIN DUONG"),
    "UNCERTAIN": ((150, 150, 150), "KHONG CHAC CHAN"),
}

REASON_TEXT = {
    "NO_FACE": "khong thay mat",
    "LOW_LIGHT": "thieu sang",
    "BLUR": "anh mo/rung",
    "EXTREME_YAW": "quay dau qua 40 do",
}


def _fmt(v, f="{:.2f}"):
    return "--" if v is None or (isinstance(v, float) and np.isnan(v)) else f.format(v)


class HUD:
    def __init__(self, history_s=10.0):
        self.ear_hist = deque()
        self.history_s = history_s
        self.show_mesh = True
        self.fps = 0.0
        self._last = None

    def draw(self, frame, r, cam, recording=False, source_label="LIVE"):
        h, w = frame.shape[:2]
        t = r["t"]
        if self._last is not None and t > self._last:
            self.fps = 0.9 * self.fps + 0.1 * (1.0 / (t - self._last)) if self.fps else 1.0 / (t - self._last)
        self._last = t
        self.ear_hist.append((t, r["ear"], r.get("closed_thr", np.nan), r["state"]))
        while self.ear_hist and self.ear_hist[0][0] < t - self.history_s:
            self.ear_hist.popleft()

        px = r.get("px")
        if px is not None:
            if self.show_mesh:
                for idx in F.RIGHT_EYE + F.LEFT_EYE + F.MOUTH:
                    cv2.circle(frame, (int(px[idx][0]), int(px[idx][1])), 2, (0, 255, 255), -1)
                for idx in IMAGE_IDS:
                    cv2.circle(frame, (int(px[idx][0]), int(px[idx][1])), 3, (255, 0, 255), -1)
            if r.get("rvec") is not None:
                draw_axes(frame, r["rvec"], r["tvec"], cam, px[1])
            x0, y0, x1, y1 = r["bbox"]
            cv2.rectangle(frame, (x0, y0), (x1, y1), (255, 255, 255), 1)

        color, label = STATE_STYLE.get(r["state"], ((255, 255, 255), r["state"]))
        if r["state"] == "CALIBRATING":
            label += f" {int(100 * r.get('calib_progress', 0))}%"
        reasons = [REASON_TEXT.get(x, x) for x in str(r.get("reasons") or "").split("|") if x]
        if reasons:
            label += " (" + ", ".join(reasons) + ")"
        # Banner trạng thái
        cv2.rectangle(frame, (0, 0), (w, 48), color, -1)
        cv2.putText(frame, label, (12, 33), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)
        if r["state"] in ("DROWSY", "DISTRACTED") and int(t * 4) % 2 == 0:
            cv2.rectangle(frame, (0, 0), (w - 1, h - 1), color, 12)

        # Bảng số đo
        lines = [
            f"EAR {_fmt(r['ear'])} (nguong {_fmt(r.get('closed_thr'))})  model {_fmt(r.get('blink_bs'))} (>0.5)"
            f"  nham {_fmt(r['closed_s'], '{:.1f}')}s",
            f"PERCLOS {_fmt(100 * r['perclos'], '{:.0f}')}%  chop mat {int(r['blinks'] or 0)}  ngap {int(r['yawns'] or 0)}",
            f"huong nhin lech: ngang {_fmt(r.get('yaw_rel'), '{:+.0f}')} = dau {_fmt(r['yaw'], '{:+.0f}')}"
            f" + mat {_fmt(r.get('eye_yaw'), '{:+.0f}')} (tru tu the goc)  doc {_fmt(r.get('pitch_rel'), '{:+.0f}')}"
            f"  +-{_fmt(r.get('pose_std'), '{:.1f}')}",
            f"khoang cach {_fmt(r['dist_cm'], '{:.0f}')} cm   sang {_fmt(r['brightness'], '{:.0f}')}"
            f"  net {_fmt(r['sharpness'], '{:.0f}')}",
            f"{source_label}  {self.fps:4.1f} FPS  tre {_fmt(r['latency_ms'], '{:.0f}')} ms"
            f" (model {_fmt(r['infer_ms'], '{:.0f}')} ms)",
        ]
        panel_h = 22 * len(lines) + 12
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, h - panel_h), (int(w * 0.62), h), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        for i, line in enumerate(lines):
            cv2.putText(frame, line, (10, h - panel_h + 22 * (i + 1)), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (255, 255, 255), 1, cv2.LINE_AA)
        self._draw_ear_plot(frame, t)
        if recording:
            cv2.circle(frame, (w - 22, 70), 9, (0, 0, 255), -1)
            cv2.putText(frame, "REC", (w - 70, 76), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1, cv2.LINE_AA)
        return frame

    def _draw_ear_plot(self, frame, t):
        h, w = frame.shape[:2]
        pw, ph = int(w * 0.34), 90
        x0, y0 = w - pw - 10, h - ph - 10
        overlay = frame.copy()
        cv2.rectangle(overlay, (x0, y0), (x0 + pw, y0 + ph), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)
        cv2.putText(frame, f"EAR {int(self.history_s)}s", (x0 + 4, y0 + 14), cv2.FONT_HERSHEY_SIMPLEX, 0.4,
                    (200, 200, 200), 1)
        ymax = 0.45

        def pt(tt, v):
            return (int(x0 + pw * (1 - (t - tt) / self.history_s)), int(y0 + ph - ph * min(v, ymax) / ymax))

        prev = None
        for tt, v, thr, st in self.ear_hist:
            if v is None or np.isnan(v):
                prev = None
                continue
            p = pt(tt, v)
            if prev is not None:
                c = (0, 0, 255) if st == "DROWSY" else (0, 255, 255)
                cv2.line(frame, prev, p, c, 1)
            prev = p
        if self.ear_hist and not np.isnan(self.ear_hist[-1][2]):
            y = pt(t, self.ear_hist[-1][2])[1]
            cv2.line(frame, (x0, y), (x0 + pw, y), (0, 128, 255), 1)
