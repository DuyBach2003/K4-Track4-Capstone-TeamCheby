"""Kiểm tra nhanh trên ĐÚNG máy demo / phòng demo (checklist mục 1). Chỉ ghi số, không lưu ảnh.

    python scripts/live_check.py --seconds 15        # ngồi yên, nhìn thẳng vào màn hình

Đo: FPS thật của webcam, độ trễ frame -> quyết định, % frame thấy mặt, độ sáng/độ nét vùng mặt,
và độ rung góc đầu giữa 2 frame liên tiếp trước/sau Kalman (Kalman có làm mượt thật không, trên dữ liệu thật).
Kết quả lưu ở reports/live_check/<thời gian>.json và in ra màn hình.
"""
import argparse
import json
import os
import platform
import sys
import time
from collections import Counter
from datetime import datetime

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dms.config import DMSConfig  # noqa: E402
from dms.pipeline import DMSPipeline  # noqa: E402


def jitter(x):
    """Độ rung giữa 2 frame liên tiếp (độ lệch chuẩn của chênh lệch): đo nhiễu, không bị chuyển động chậm làm sai."""
    d = np.diff(x)
    d = d[np.isfinite(d)]
    return float(np.std(d)) if len(d) > 2 else float("nan")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--seconds", type=float, default=15.0)
    args = ap.parse_args()

    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    if not cap.isOpened():
        raise SystemExit("Không mở được camera. Trên macOS: cấp quyền Camera cho Terminal/VS Code.")
    pipe = DMSPipeline(DMSConfig(model_path=os.path.join(ROOT, "models/face_landmarker.task")))
    rows = []
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < args.seconds:
        ok, frame = cap.read()
        t_cap = time.perf_counter()
        if not ok:
            break
        r = pipe.process(frame, t_cap - t0, t_cap)
        rows.append({k: v for k, v in r.items() if k not in ("px", "rvec", "tvec", "bbox")})
    pipe.close()
    cap.release()
    if len(rows) < 10:
        raise SystemExit("Quá ít frame")

    g = lambda k: np.array([r[k] for r in rows], float)  # noqa: E731
    t = g("t")
    still = (t > DMSConfig().calib_seconds) & (g("face") == 1)   # bỏ giai đoạn hiệu chuẩn
    res = {
        "machine": platform.node(), "time": datetime.now().isoformat(timespec="seconds"),
        "resolution": f"{frame.shape[1]}x{frame.shape[0]}", "frames": len(rows),
        "fps": (len(t) - 1) / (t[-1] - t[0]),
        "latency_ms_p50": float(np.percentile(g("latency_ms"), 50)),
        "latency_ms_p95": float(np.percentile(g("latency_ms"), 95)),
        "infer_ms_p50": float(np.percentile(g("infer_ms"), 50)),
        "face_pct": float(100 * np.mean(g("face") == 1)),
        "brightness_median": float(np.nanmedian(g("brightness"))),
        "sharpness_median": float(np.nanmedian(g("sharpness"))),
        "open_ear": float(rows[-1]["open_ear"]),
        "dist_cm_median": float(np.nanmedian(g("dist_cm"))),
        "yaw_jitter_raw_deg": jitter(g("yaw_raw")[still]),
        "yaw_jitter_kf_deg": jitter(g("yaw")[still]),
        "pitch_jitter_raw_deg": jitter(g("pitch_raw")[still]),
        "pitch_jitter_kf_deg": jitter(g("pitch")[still]),
        "states": dict(Counter(r["state"] for r in rows)),
    }
    os.makedirs(os.path.join(ROOT, "reports/live_check"), exist_ok=True)
    out = os.path.join(ROOT, "reports/live_check", datetime.now().strftime("%Y%m%d_%H%M%S") + ".json")
    with open(out, "w") as f:
        json.dump(res, f, indent=2, ensure_ascii=False)
    for k, v in res.items():
        print(f"{k:22s} {v:.2f}" if isinstance(v, float) else f"{k:22s} {v}")
    print("đã lưu", out)


if __name__ == "__main__":
    main()
