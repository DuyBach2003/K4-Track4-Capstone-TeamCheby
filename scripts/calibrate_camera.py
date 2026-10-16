"""HÌNH HỌC (tuỳ chọn): hiệu chuẩn webcam bằng bàn cờ để có ma trận K thật thay cho f ~ 0.85 W.

In hoặc mở ảnh bàn cờ 9x6 ô góc trong (vd. https://github.com/opencv/opencv/blob/4.x/doc/pattern.png) trên điện thoại,
đưa trước camera ở nhiều góc. Bấm SPACE để chụp (cần >= 12 ảnh), q để tính.

    python scripts/calibrate_camera.py --square-mm 24
    python app.py --camera-matrix models/camera_K.npz

benchmark (scripts/bench_headpose.py) cho thấy sai f ±30% chỉ làm góc lệch < 1.5 độ nhưng làm khoảng cách sai ~30%,
nên bước này chủ yếu cần nếu muốn dùng số đo khoảng cách.
"""
import argparse

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("--camera", type=int, default=0)
ap.add_argument("--cols", type=int, default=9)
ap.add_argument("--rows", type=int, default=6)
ap.add_argument("--square-mm", type=float, default=24.0)
ap.add_argument("--out", default="models/camera_K.npz")
args = ap.parse_args()

pattern = (args.cols, args.rows)
objp = np.zeros((args.cols * args.rows, 3), np.float32)
objp[:, :2] = np.mgrid[0:args.cols, 0:args.rows].T.reshape(-1, 2) * args.square_mm
obj_pts, img_pts = [], []
cap = cv2.VideoCapture(args.camera)
size = None
while True:
    ok, frame = cap.read()
    if not ok:
        break
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    size = gray.shape[::-1]
    found, corners = cv2.findChessboardCorners(gray, pattern, None)
    vis = frame.copy()
    if found:
        cv2.drawChessboardCorners(vis, pattern, corners, found)
    cv2.putText(vis, f"anh: {len(obj_pts)}  SPACE chup, q tinh", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.imshow("calib", vis)
    k = cv2.waitKey(1) & 0xFF
    if k == ord(" ") and found:
        corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1),
                                   (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001))
        obj_pts.append(objp)
        img_pts.append(corners)
    elif k == ord("q"):
        break
cap.release()
cv2.destroyAllWindows()
if len(obj_pts) < 8:
    raise SystemExit("Cần ít nhất 8 ảnh bàn cờ")
rms, K, dist, _, _ = cv2.calibrateCamera(obj_pts, img_pts, size, None, None)
np.savez(args.out, K=K, dist=dist, size=size)
print(f"RMS reprojection error {rms:.3f} px")
print(f"K =\n{K}\n=> focal_scale thực = {K[0, 0] / size[0]:.3f} (mặc định đang giả định 0.85)")
print("đã lưu", args.out)
