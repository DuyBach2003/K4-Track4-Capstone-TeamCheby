"""BẰNG CHỨNG cho trụ cột HÌNH HỌC: solvePnP sai bao nhiêu độ khi
  (a) mốc mặt bị nhiễu (jitter của MediaPipe), và
  (b) tiêu cự f giả định sai (vì không hiệu chuẩn camera thật)?

Cách đo: chiếu mô hình mặt 3D với góc đã biết bằng camera "thật" (f_true), thêm nhiễu Gauss vào điểm ảnh,
rồi giải ngược bằng camera "giả định" (f_assumed) -> so sánh với góc thật. Monte Carlo, có seed để lặp lại được.

    python scripts/bench_headpose.py
"""
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dms.head_pose import IMAGE_IDS, camera_matrix, estimate_head_pose, project_model  # noqa: E402

W, H = 1280, 720
OUT = "reports/headpose_bench"


def run_case(f_true, f_assumed, noise_px, yaws, pitches, n=20, seed=0, dist=60.0):
    rng = np.random.default_rng(seed)
    cam_t, cam_a = camera_matrix(W, H, f_true), camera_matrix(W, H, f_assumed)
    errs, derr = [], []
    for yaw in yaws:
        for pitch in pitches:
            pts = project_model(yaw, pitch, 0.0, cam_t, dist)
            for _ in range(n):
                px = np.zeros((478, 2))
                px[IMAGE_IDS] = pts + rng.normal(0, noise_px, pts.shape)
                est = estimate_head_pose(px, cam_a)
                errs.append([abs(est[0] - yaw), abs(est[1] - pitch)])
                derr.append(abs(np.linalg.norm(est[4]) - dist) / dist * 100)
    e = np.array(errs)
    return {"yaw_mae": float(e[:, 0].mean()), "pitch_mae": float(e[:, 1].mean()),
            "yaw_p95": float(np.percentile(e[:, 0], 95)), "pitch_p95": float(np.percentile(e[:, 1], 95)),
            "dist_err_pct": float(np.mean(derr))}


def main():
    os.makedirs(OUT, exist_ok=True)
    yaws = np.arange(-60, 61, 10)
    pitches = np.arange(-30, 31, 10)
    rows = []
    for noise in (0.0, 1.0, 2.0, 4.0):
        rows.append({"case": "noise", "noise_px": noise, "f_err_pct": 0, **run_case(0.85, 0.85, noise, yaws, pitches)})
    for f_err in (-30, -15, 15, 30):
        rows.append({"case": "focal", "noise_px": 1.0, "f_err_pct": f_err,
                     **run_case(0.85, 0.85 * (1 + f_err / 100), 1.0, yaws, pitches)})
    # Sai số theo từng góc yaw (nhiễu 2 px) -> cho thấy góc càng lớn càng kém tin
    per_yaw = []
    for yaw in yaws:
        r = run_case(0.85, 0.85, 2.0, [yaw], pitches, n=40)
        per_yaw.append({"yaw": int(yaw), **r})

    with open(f"{OUT}/results.json", "w") as f:
        json.dump({"rows": rows, "per_yaw": per_yaw}, f, indent=2)

    lines = ["# Benchmark solvePnP (dữ liệu tổng hợp, có thể chạy lại: `python scripts/bench_headpose.py`)", "",
             f"Ảnh {W}x{H}, mặt cách camera 60 cm, yaw -60..60, pitch -30..30 (bước 10 độ), 20 lần lặp mỗi góc.", "",
             "| Điều kiện | nhiễu mốc (px) | sai f (%) | yaw MAE (độ) | pitch MAE (độ) | yaw p95 | pitch p95 | sai khoảng cách (%) |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['case']} | {r['noise_px']:.0f} | {r['f_err_pct']:+d} | {r['yaw_mae']:.2f} | "
                     f"{r['pitch_mae']:.2f} | {r['yaw_p95']:.2f} | {r['pitch_p95']:.2f} | {r['dist_err_pct']:.1f} |")
    lines += ["", "Sai số theo yaw (nhiễu 2 px):", "", "| yaw | yaw MAE | pitch MAE |", "|---|---|---|"]
    for r in per_yaw:
        lines.append(f"| {r['yaw']:+d} | {r['yaw_mae']:.2f} | {r['pitch_mae']:.2f} |")
    open(f"{OUT}/README.md", "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
        nr = [r for r in rows if r["case"] == "noise"]
        ax[0].plot([r["noise_px"] for r in nr], [r["yaw_mae"] for r in nr], "o-", label="yaw")
        ax[0].plot([r["noise_px"] for r in nr], [r["pitch_mae"] for r in nr], "s-", label="pitch")
        ax[0].set_xlabel("nhiễu mốc mặt (px)"); ax[0].set_ylabel("MAE (độ)"); ax[0].set_title("Ảnh hưởng nhiễu")
        ax[0].legend(); ax[0].grid(alpha=.3)
        ax[1].plot([r["yaw"] for r in per_yaw], [r["yaw_mae"] for r in per_yaw], "o-", label="yaw")
        ax[1].plot([r["yaw"] for r in per_yaw], [r["pitch_mae"] for r in per_yaw], "s-", label="pitch")
        ax[1].axvspan(-30, 30, color="green", alpha=.08, label="vùng 'nhìn đường'")
        ax[1].set_xlabel("yaw thật (độ)"); ax[1].set_title("Sai số theo góc quay (nhiễu 2 px)")
        ax[1].legend(); ax[1].grid(alpha=.3)
        fig.tight_layout(); fig.savefig(f"{OUT}/bench.png", dpi=130)
    except ImportError:
        pass


if __name__ == "__main__":
    main()
