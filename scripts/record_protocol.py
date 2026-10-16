"""DỮ LIỆU: thu video có nhãn theo kịch bản. Thành viên team tự đóng vai (không dùng dữ liệu người khác).

    python scripts/record_protocol.py --protocol main --name bach
    python scripts/record_protocol.py --protocol failure --name bach

Tạo ra trong recordings/:
    <protocol>_<name>_<time>.mp4          video gốc (không vẽ gì lên)
    <protocol>_<name>_<time>_frames.csv   timestamp thật từng frame (FPS webcam không đều)
    <protocol>_<name>_<time>_labels.csv   các đoạn nhãn (start, end, eye, attention, prompt, expect)

Mỗi lần đổi đoạn sẽ có tiếng "tink" để người đóng vai biết mở mắt khi đang nhắm.
Lời nhắc của đoạn kế tiếp hiện trước 2 s để kịp chuẩn bị.
"""
import argparse
import csv
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from protocols import segments  # noqa: E402


def beep():
    snd = "/System/Library/Sounds/Tink.aiff"
    if platform.system() == "Darwin" and shutil.which("afplay") and os.path.exists(snd):
        subprocess.Popen(["afplay", snd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        print("\a", end="", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--protocol", default="main", choices=["main", "failure"])
    ap.add_argument("--name", default="member")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--countdown", type=float, default=5.0)
    args = ap.parse_args()

    segs = segments(args.protocol)
    total = segs[-1]["end"]
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    ok, frame = cap.read()
    if not ok:
        raise SystemExit("Không mở được camera")
    h, w = frame.shape[:2]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    os.makedirs("recordings", exist_ok=True)
    base = f"recordings/{args.protocol}_{args.name}_{stamp}"
    writer = cv2.VideoWriter(base + ".mp4", cv2.VideoWriter_fourcc(*"mp4v"), 30, (w, h))

    with open(base + "_labels.csv", "w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(segs[0].keys()))
        wr.writeheader()
        wr.writerows(segs)

    # Đếm ngược (không ghi)
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < args.countdown:
        ok, frame = cap.read()
        vis = cv2.flip(frame, 1)
        left = args.countdown - (time.perf_counter() - t0)
        cv2.putText(vis, f"Bat dau sau {left:.0f}s - ngoi nhu dang lai xe", (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 1,
                    (0, 255, 255), 2)
        cv2.putText(vis, "Dau tien: " + segs[0]["prompt"], (30, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow("Thu du lieu DMS", vis)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            return

    frames = []
    t_start = time.perf_counter()
    seg_i = -1
    i = 0
    while True:
        ok, frame = cap.read()
        t = time.perf_counter() - t_start
        if not ok or t > total:
            break
        writer.write(frame)
        frames.append((i, round(t, 4)))
        i += 1
        cur = next(k for k, s in enumerate(segs) if s["start"] <= t < s["end"]) if t < total else len(segs) - 1
        if cur != seg_i:
            seg_i = cur
            beep()
        s = segs[cur]
        vis = cv2.flip(frame, 1)
        color = (0, 0, 255) if s["eye"] == "closed" or s["attention"] == "away" else (0, 200, 0)
        cv2.rectangle(vis, (0, 0), (w, 80), color, -1)
        cv2.putText(vis, s["prompt"], (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis, f"{s['end'] - t:4.1f}s", (w - 120, 52), cv2.FONT_HERSHEY_SIMPLEX, 1.1, (255, 255, 255), 2)
        if cur + 1 < len(segs) and s["end"] - t < 2.0:
            cv2.putText(vis, "Tiep theo: " + segs[cur + 1]["prompt"], (20, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                        (0, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(vis, f"REC {t:5.1f}/{total:.0f}s", (20, 115), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.imshow("Thu du lieu DMS", vis)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("Dừng sớm - dữ liệu vẫn được lưu nhưng các đoạn sau sẽ thiếu.")
            break

    cap.release()
    writer.release()
    cv2.destroyAllWindows()
    with open(base + "_frames.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["frame", "t"])
        wr.writerows(frames)
    fps = len(frames) / frames[-1][1] if frames and frames[-1][1] > 0 else 0
    print(f"Đã lưu {base}.mp4 ({len(frames)} frame, {fps:.1f} FPS thực)")
    print(f"Chấm điểm: python scripts/evaluate.py {base}.mp4")


if __name__ == "__main__":
    main()
