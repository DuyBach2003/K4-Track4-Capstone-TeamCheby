"""VinFast Driver Monitoring System (DMS) - demo trực tiếp.

    python app.py                         # webcam 0
    python app.py --source 1              # camera khác
    python app.py --source clip.mp4       # replay video (video dự phòng / ca lỗi)
    python app.py --save-video            # ghi lại video đã vẽ HUD để làm video dự phòng

Phím: q/ESC thoát | c hiệu chuẩn lại | r bật/tắt ghi video | m ẩn/hiện mốc | s bật/tắt âm thanh | space tạm dừng
"""
import argparse
import os
import time
from datetime import datetime

import cv2
import numpy as np

from dms.config import DMSConfig
from dms.hud import HUD
from dms.io_utils import Alarm, CSVLogger, make_writer
from dms.pipeline import DMSPipeline


def open_source(src):
    if src.isdigit():
        cap = cv2.VideoCapture(int(src))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        return cap, True
    if not os.path.exists(src):
        raise SystemExit(f"Không tìm thấy {src}")
    return cv2.VideoCapture(src), False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", default="0")
    ap.add_argument("--log", default="", help="đường dẫn CSV (mặc định logs/session_<thời gian>.csv)")
    ap.add_argument("--save-video", action="store_true", help="ghi video có HUD ngay từ đầu")
    ap.add_argument("--no-sound", action="store_true")
    ap.add_argument("--no-window", action="store_true", help="chạy không mở cửa sổ (replay để lấy log)")
    ap.add_argument("--mirror", action="store_true", help="lật ảnh như gương (chỉ để hiển thị)")
    ap.add_argument("--focal-scale", type=float, default=None)
    ap.add_argument("--camera-matrix", default="", help="file .npz từ scripts/calibrate_camera.py")
    args = ap.parse_args()

    cfg = DMSConfig()
    cfg.sound = not args.no_sound
    if args.focal_scale:
        cfg.focal_scale = args.focal_scale
    if args.camera_matrix:
        cfg.camera_matrix_path = args.camera_matrix

    cap, live = open_source(args.source)
    if not cap.isOpened():
        raise SystemExit("Không mở được camera/video. Trên macOS: cấp quyền Camera cho Terminal/VS Code.")
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_path = args.log or f"logs/session_{stamp}.csv"
    logger = CSVLogger(log_path)
    pipe = DMSPipeline(cfg)
    hud = HUD()
    alarm = Alarm(cfg.sound, cfg.sound_cooldown_s)
    writer, recording = None, args.save_video
    t_start = time.perf_counter()
    paused = False
    frame_i = 0
    lat, t_hist = [], []
    print(f"[DMS] nguồn={args.source} log={log_path}")

    try:
        while True:
            if not paused:
                ok, frame = cap.read()
                t_cap = time.perf_counter()
                if not ok:
                    break
                # Live: dùng đồng hồ thật. Replay: dùng thời gian của video để kết quả lặp lại được.
                t = (t_cap - t_start) if live else frame_i / video_fps
                frame_i += 1
                r = pipe.process(frame, t, t_cap)
                logger.write(r)
                lat.append(r["latency_ms"])
                t_hist.append(t_cap)
                if r["state"] in ("DROWSY", "DISTRACTED"):
                    alarm.trigger(r["state"])
                vis = hud.draw(frame.copy(), r, pipe.cam, recording, "LIVE" if live else "REPLAY")
                if args.mirror:
                    vis = cv2.flip(vis, 1)
                # Live: FPS ghi phải bằng FPS thật đo được, nếu không video phát nhanh/chậm và "báo sau 1 s"
                # trong video dự phòng sẽ sai. Đợi 30 frame để có FPS đo được rồi mới mở file.
                if recording and (not live or len(t_hist) > 30):
                    if writer is None:
                        os.makedirs("recordings", exist_ok=True)
                        fps_out = (len(t_hist) - 1) / (t_hist[-1] - t_hist[0]) if live else video_fps
                        writer = make_writer(f"recordings/demo_{stamp}.mp4", fps_out, (vis.shape[1], vis.shape[0]))
                    writer.write(vis)
            if args.no_window:
                continue
            cv2.imshow("VinFast DMS - Team Cheby", vis)
            key = cv2.waitKey(1 if live else max(1, int(1000 / video_fps))) & 0xFF
            if key in (ord("q"), 27):
                break
            if key == ord("c"):
                pipe.recalibrate()
            elif key == ord("r"):
                recording = not recording
            elif key == ord("m"):
                hud.show_mesh = not hud.show_mesh
            elif key == ord("s"):
                alarm.enabled = not alarm.enabled
            elif key == ord(" "):
                paused = not paused
    finally:
        cap.release()
        logger.close()
        pipe.close()
        if writer is not None:
            writer.release()
        cv2.destroyAllWindows()
        print(f"[DMS] đã lưu log: {log_path}")
        if len(lat) > 10:
            fps = (len(t_hist) - 1) / (t_hist[-1] - t_hist[0])
            print(f"[DMS] {len(lat)} frame | FPS đầu vào {fps:.1f} | độ trễ xử lý p50 {np.percentile(lat, 50):.1f} ms"
                  f" p95 {np.percentile(lat, 95):.1f} ms | vẽ biểu đồ: python scripts/plot_session.py {log_path}")


if __name__ == "__main__":
    main()
