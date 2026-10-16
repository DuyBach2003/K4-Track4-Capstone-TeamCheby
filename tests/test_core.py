import math

import numpy as np
import pytest

from dms.config import DMSConfig
from dms.features import eye_aspect_ratio, mouth_aspect_ratio
from dms.head_pose import MODEL_POINTS, IMAGE_IDS, camera_matrix, estimate_head_pose, project_model
from dms.kalman import ConstantVelocityKF
from dms.state import DISTRACTED, DROWSY, OK, CALIBRATING, UNCERTAIN, TemporalStateMachine

CAM = camera_matrix(1280, 720, 0.85)


def fake_px(yaw, pitch, roll, noise=0.0, seed=0):
    """Tạo mảng 478 mốc giả chỉ có các điểm solvePnP dùng."""
    px = np.zeros((478, 2))
    pts = project_model(yaw, pitch, roll, CAM)
    if noise:
        pts = pts + np.random.default_rng(seed).normal(0, noise, pts.shape)
    px[IMAGE_IDS] = pts
    return px


# ---------- Biểu diễn ----------
def test_ear_open_vs_closed():
    open_eye = np.array([[0, 0], [10, -4], [20, -4], [30, 0], [20, 4], [10, 4]], float)
    closed_eye = open_eye * np.array([1, 0.1])
    assert eye_aspect_ratio(open_eye) == pytest.approx(8 / 30)
    assert eye_aspect_ratio(closed_eye) < 0.05


def test_mar():
    assert mouth_aspect_ratio(np.array([[0, 0], [40, 0], [20, -15], [20, 15]], float)) == pytest.approx(0.75)


# ---------- Hình học ----------
@pytest.mark.parametrize("yaw,pitch,roll", [(0, 0, 0), (30, 0, 0), (-30, 10, 0), (0, -25, 5), (45, -15, -10)])
def test_solvepnp_recovers_known_pose(yaw, pitch, roll):
    est = estimate_head_pose(fake_px(yaw, pitch, roll), CAM)
    assert est is not None
    assert est[0] == pytest.approx(yaw, abs=0.5)
    assert est[1] == pytest.approx(pitch, abs=0.5)
    assert est[2] == pytest.approx(roll, abs=0.5)
    assert np.linalg.norm(est[4]) == pytest.approx(60.0, rel=0.02)   # khoảng cách cm


def test_yaw_sign_convention():
    # yaw > 0: mũi lệch về phía trái ảnh so với điểm giữa hai khoé mắt
    px = fake_px(30, 0, 0)
    mid_eyes = (px[33] + px[263]) / 2
    assert px[1][0] < mid_eyes[0]


def test_model_has_rigid_points_only():
    assert 152 not in IMAGE_IDS and 13 not in IMAGE_IDS and 14 not in IMAGE_IDS   # không cằm, không môi
    assert MODEL_POINTS.shape == (len(IMAGE_IDS), 3)


# ---------- Thời gian / Kalman ----------
def test_kalman_reduces_jitter_and_handles_variable_dt():
    rng = np.random.default_rng(1)
    kf = ConstantVelocityKF(400.0, 4.0)
    t, truth, raw, filt = 0.0, [], [], []
    for i in range(300):
        dt = 1 / 30 if i % 3 else 1 / 15          # FPS dao động
        t += dt
        x = 20 * math.sin(0.5 * t)
        z = x + rng.normal(0, 2.0)
        truth.append(x); raw.append(z); filt.append(kf.update(z, dt))
    truth, raw, filt = map(np.array, (truth, raw, filt))
    rmse_raw = np.sqrt(np.mean((raw[30:] - truth[30:]) ** 2))
    rmse_kf = np.sqrt(np.mean((filt[30:] - truth[30:]) ** 2))
    assert rmse_kf < 0.75 * rmse_raw


def test_kalman_predict_grows_uncertainty():
    kf = ConstantVelocityKF()
    for _ in range(20):
        kf.update(10.0, 1 / 30)
    s0 = kf.std
    for _ in range(10):
        kf.predict(1 / 30)
    assert kf.std > s0


# ---------- Máy trạng thái ----------
def run(sm, seq, fps=30):
    """seq: list (duration_s, face_dict_or_None, reasons)"""
    t, out = 0.0, []
    for dur, face, reasons in seq:
        for _ in range(int(dur * fps)):
            out.append((t, sm.update(t, face, reasons)))
            t += 1 / fps
    return out


def face(ear=0.30, yaw=0.0, pitch=0.0, mar=0.1):
    return {"ear": ear, "yaw": yaw, "pitch": pitch, "mar": mar}


def test_calibration_then_ok():
    sm = TemporalStateMachine(DMSConfig())
    out = run(sm, [(1.0, face(), []), (3.0, face(), [])])
    assert out[10][1].state == CALIBRATING
    assert out[-1][1].state == OK
    assert out[-1][1].closed_thr == pytest.approx(0.30 * 0.65)


def test_blink_is_not_alarm_but_long_closure_is():
    sm = TemporalStateMachine(DMSConfig())
    out = run(sm, [(3.5, face(), []), (0.2, face(ear=0.08), []), (1.0, face(), []), (1.5, face(ear=0.08), [])])
    states = [o.state for _, o in out]
    t_alarm = next(t for t, o in out if o.state == DROWSY)
    assert out[-1][1].blinks == 1
    # nhắm bắt đầu ở t=4.7 s -> báo sau đúng 1.0 s (sai số 1 frame)
    assert t_alarm == pytest.approx(4.7 + 1.0, abs=0.05)
    assert DROWSY not in states[: int(5.6 * 30)]


def test_fps_independence():
    """Cùng kịch bản ở 15 FPS và 30 FPS phải báo động ở cùng thời điểm (vì đếm theo giây)."""
    times = []
    for fps in (15, 30):
        sm = TemporalStateMachine(DMSConfig())
        out = run(sm, [(3.5, face(), []), (2.0, face(ear=0.05), [])], fps=fps)
        times.append(next(t for t, o in out if o.state == DROWSY))
    assert abs(times[0] - times[1]) <= 1 / 15 + 1e-6


def test_distraction_relative_to_neutral_pose():
    sm = TemporalStateMachine(DMSConfig())
    # Camera gắn thấp: lúc nhìn đường pitch tuyệt đối đã là -25 độ -> không được báo xao nhãng
    out = run(sm, [(3.5, face(pitch=-25), []), (3.0, face(pitch=-25), [])])
    assert out[-1][1].state == OK
    out = run(sm, [(2.5, face(yaw=40, pitch=-25), [])])
    assert out[-1][1].state == DISTRACTED


def test_low_light_is_uncertain_not_ok_and_no_false_drowsy():
    sm = TemporalStateMachine(DMSConfig())
    out = run(sm, [(3.5, face(), []), (3.0, face(ear=0.05), ["LOW_LIGHT"])])
    states = {o.state for _, o in out[-60:]}
    assert states == {UNCERTAIN}


def test_perclos_needs_enough_history_before_fatigue():
    """Lỗi tìm ra khi chạy webcam thật: ngay sau hiệu chuẩn, vài cái chớp mắt đã làm PERCLOS > 15% -> FATIGUE giả."""
    from dms.state import FATIGUE
    sm = TemporalStateMachine(DMSConfig())
    # sau hiệu chuẩn (xong ở t=3 s): chớp 0.3 s mỗi 1.5 s = 20% thời gian nhắm, kéo dài 24 s
    blinky = [(1.2, face(), []), (0.3, face(ear=0.08), [])] * 16
    out = run(sm, [(3.5, face(), [])] + blinky)
    t_first = next(t for t, o in out if o.state == FATIGUE)
    assert t_first >= 3.0 + DMSConfig().perclos_min_history_s - 0.1
    assert out[-1][1].state == FATIGUE
