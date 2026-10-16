"""Vẽ biểu đồ từ log CSV của một phiên chạy app.py (EAR, góc đầu, độ trễ, trạng thái).

    python scripts/plot_session.py logs/session_20261016_180000.csv
"""
import csv
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evaluate import plot  # noqa: E402

NUMERIC_SKIP = {"state", "reasons"}


def load(path):
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            rows.append({k: (v if k in NUMERIC_SKIP else (float(v) if v != "" else np.nan)) for k, v in r.items()})
    return rows


if __name__ == "__main__":
    path = sys.argv[1]
    rows = load(path)
    out = os.path.splitext(path)[0] + ".png"
    plot(rows, [], out)
    lat = np.array([r["latency_ms"] for r in rows])
    t = np.array([r["t"] for r in rows])
    states = [r["state"] for r in rows]
    print(f"{len(rows)} frame, {t[-1] - t[0]:.1f} s, FPS {(len(t) - 1) / (t[-1] - t[0]):.1f}, "
          f"trễ p50 {np.nanpercentile(lat, 50):.1f} ms p95 {np.nanpercentile(lat, 95):.1f} ms")
    for s in sorted(set(states)):
        print(f"  {s:12s} {100 * states.count(s) / len(states):5.1f}%")
    print("đã lưu", out)
