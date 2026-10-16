"""BẰNG CHỨNG: chạy lại (replay) video thu theo kịch bản qua đúng pipeline của demo rồi so với nhãn.

    python scripts/evaluate.py recordings/main_bach_20261016_180000.mp4

Đầu ra trong reports/<tên video>/ : log.csv, metrics.json, metrics.md, timeline.png

Cách chấm (giải thích được khi hội đồng hỏi):
  * Nhãn = lời nhắc trên màn hình. Người cần ~0.5 s để phản ứng sau tiếng "tink", nên bỏ 0.7 s đầu mỗi đoạn
    khi chấm theo frame (REACTION_S).
  * Theo frame: mắt nhắm/mở, so 2 cách: (1) hệ thống (EAR cá nhân hoá VÀ blendshape cùng đồng ý),
    (2) chỉ blendshape eyeBlink của MediaPipe (một đầu ra "học" sẵn) > 0.5.
  * Theo sự kiện: mỗi đoạn mong đợi DROWSY/DISTRACTED có báo động không, trễ bao lâu kể từ lúc bắt đầu đoạn
    (trễ này GỒM cả thời gian phản ứng của người đóng vai + ngưỡng 1 s / 2 s cố ý của hệ thống).
  * Báo động giả: số lần chuyển sang DROWSY/DISTRACTED trong các đoạn mong đợi OK.
"""
import argparse
import csv
import json
import os
import sys
import time

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from dms.config import DMSConfig  # noqa: E402
from dms.io_utils import CSVLogger  # noqa: E402
from dms.pipeline import DMSPipeline  # noqa: E402

REACTION_S = 0.7
ALARMS = ("DROWSY", "DISTRACTED")
STATE_COLORS = {"CALIBRATING": "#c8a000", "OK": "#3caa3c", "FATIGUE": "#ffbe00", "DROWSY": "#e0201b",
                "DISTRACTED": "#ff5a00", "UNCERTAIN": "#969696"}


def load_labels(base):
    with open(base + "_labels.csv") as f:
        segs = list(csv.DictReader(f))
    for s in segs:
        s["start"], s["end"] = float(s["start"]), float(s["end"])
    return segs


def load_times(base, n_hint, fps):
    p = base + "_frames.csv"
    if os.path.exists(p):
        with open(p) as f:
            return [float(r["t"]) for r in csv.DictReader(f)]
    return [i / fps for i in range(n_hint)]


def run_pipeline(video, times, log_path):
    cap = cv2.VideoCapture(video)
    pipe = DMSPipeline(DMSConfig())
    logger = CSVLogger(log_path)
    rows = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok or i >= len(times):
            break
        t_cap = time.perf_counter()
        r = pipe.process(frame, times[i], t_cap)
        logger.write(r)
        rows.append({k: v for k, v in r.items() if k not in ("px", "rvec", "tvec", "bbox")})
        i += 1
    cap.release()
    logger.close()
    pipe.close()
    return rows


def prf(gt, pred):
    gt, pred = np.asarray(gt, bool), np.asarray(pred, bool)
    tp = int((gt & pred).sum()); fp = int((~gt & pred).sum()); fn = int((gt & ~pred).sum()); tn = int((~gt & ~pred).sum())
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    f1 = 2 * p * r / (p + r) if p + r else float("nan")
    return {"precision": p, "recall": r, "f1": f1, "accuracy": (tp + tn) / max(1, len(gt)),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": len(gt)}


def seg_of(t, segs):
    for s in segs:
        if s["start"] <= t < s["end"]:
            return s
    return None


def evaluate(rows, segs):
    t = np.array([r["t"] for r in rows])
    state = [r["state"] for r in rows]
    face = np.array([r["face"] for r in rows]) == 1
    calibrated = np.array([s != "CALIBRATING" for s in state])

    # ---- theo frame: mắt ----
    gt, p_ear, p_bs = [], [], []
    for r in rows:
        s = seg_of(r["t"], segs)
        if (s is None or s["eye"] == "any" or s["attention"] == "away" or r["t"] < s["start"] + REACTION_S
                or r["face"] != 1 or r["state"] == "CALIBRATING"):
            continue
        gt.append(s["eye"] == "closed")
        p_ear.append(r["eyes_closed"] == 1)
        p_bs.append(r["blink_bs"] > 0.5 if not np.isnan(r["blink_bs"]) else False)
    eye_ear, eye_bs = prf(gt, p_ear), prf(gt, p_bs)

    # ---- theo sự kiện ----
    events = []
    for s in segs:
        if s["expect"] not in ALARMS:
            continue
        win = (t >= s["start"]) & (t <= s["end"] + 1.0)
        hit = [ti for ti, st, w in zip(t, state, win) if w and st == s["expect"]]
        events.append({"prompt": s["prompt"], "expect": s["expect"], "duration_s": s["end"] - s["start"],
                       "detected": bool(hit), "delay_s": (hit[0] - s["start"]) if hit else None})

    # ---- báo động giả ----
    false_alarms, ok_time = [], 0.0
    for s in segs:
        if s["expect"] != "OK":
            continue
        a, b = s["start"] + 1.0, s["end"]          # bỏ 1 s đầu: báo động của đoạn trước còn kéo dài hợp lệ
        ok_time += max(0.0, b - a)
        for k in range(1, len(rows)):
            if a <= t[k] < b and state[k] in ALARMS and state[k - 1] != state[k]:
                false_alarms.append({"t": float(t[k]), "state": state[k], "prompt": s["prompt"]})

    # ---- theo đoạn (để nhìn ca lỗi) ----
    seg_rows = []
    for s in segs:
        m = (t >= s["start"] + REACTION_S) & (t < s["end"])
        if not m.any():
            continue
        sub = [r for r, k in zip(rows, m) if k]
        ears = np.array([r["ear"] for r in sub], float)
        sts = [r["state"] for r in sub]
        top = max(set(sts), key=sts.count)
        got_alarm = [a for a in ALARMS if a in sts]
        if s["expect"] in ALARMS:
            ok_ = s["expect"] in got_alarm
        elif s["expect"] == "OK":
            ok_ = not got_alarm
        else:
            ok_ = None
        seg_rows.append({
            "start": s["start"], "prompt": s["prompt"], "expect": s["expect"], "main_state": top,
            "alarms": ",".join(got_alarm) or "-", "face_pct": 100 * np.mean([r["face"] == 1 for r in sub]),
            "ear_mean": float(np.nanmean(ears)) if np.isfinite(ears).any() else float("nan"),
            "closed_pct": 100 * np.mean([r["eyes_closed"] == 1 for r in sub]),
            "yaw_rel": float(np.nanmean([abs(r["yaw_rel"]) for r in sub])),
            "pitch_rel": float(np.nanmean([r["pitch_rel"] for r in sub])),
            "uncertain_pct": 100 * np.mean([x == "UNCERTAIN" for x in sts]),
            "pass": ok_,
        })

    # ---- thời gian ----
    lat = np.array([r["latency_ms"] for r in rows]); inf = np.array([r["infer_ms"] for r in rows])
    dt = np.diff(t)
    # jitter góc đầu khi ngồi yên: đoạn hiệu chuẩn (đã bỏ 1 s đầu)
    s0 = segs[0]
    m0 = (t > s0["start"] + 1.0) & (t < s0["end"]) & face
    yaw_raw = np.array([r["yaw_raw"] for r in rows])[m0]
    yaw_kf = np.array([r["yaw"] for r in rows])[m0]
    pitch_raw = np.array([r["pitch_raw"] for r in rows])[m0]
    pitch_kf = np.array([r["pitch"] for r in rows])[m0]

    def nstd(x):
        """Độ rung giữa 2 frame liên tiếp: std của chênh lệch, không bị chuyển động chậm làm sai."""
        d = np.diff(x)
        d = d[np.isfinite(d)]
        return float(np.std(d)) if len(d) > 2 else float("nan")

    det = [e for e in events if e["detected"]]
    return {
        "n_frames": len(rows), "duration_s": float(t[-1] - t[0]) if len(t) else 0.0,
        "capture_fps": float(1 / np.median(dt)) if len(dt) else float("nan"),
        "face_coverage_pct": float(100 * face.mean()),
        "calibrated_at_s": float(t[np.argmax(calibrated)]) if calibrated.any() else None,
        "eye_frames_EAR": eye_ear, "eye_frames_blendshape": eye_bs,
        "events": events,
        "event_recall": len(det) / len(events) if events else float("nan"),
        "drowsy_delay_mean_s": _mean([e["delay_s"] for e in det if e["expect"] == "DROWSY"]),
        "distract_delay_mean_s": _mean([e["delay_s"] for e in det if e["expect"] == "DISTRACTED"]),
        "false_alarms": false_alarms, "ok_time_s": ok_time,
        "false_alarms_per_min": len(false_alarms) / (ok_time / 60) if ok_time else float("nan"),
        "latency_ms_p50": float(np.percentile(lat, 50)), "latency_ms_p95": float(np.percentile(lat, 95)),
        "infer_ms_p50": float(np.percentile(inf, 50)), "infer_ms_p95": float(np.percentile(inf, 95)),
        "yaw_jitter_raw_deg": nstd(yaw_raw), "yaw_jitter_kf_deg": nstd(yaw_kf),
        "pitch_jitter_raw_deg": nstd(pitch_raw), "pitch_jitter_kf_deg": nstd(pitch_kf),
        "segments": seg_rows,
    }


def _mean(xs):
    xs = [x for x in xs if x is not None]
    return float(np.mean(xs)) if xs else None


def f(x, fmt="{:.2f}"):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    return fmt.format(x)


def write_markdown(m, path, video):
    e1, e2 = m["eye_frames_EAR"], m["eye_frames_blendshape"]
    L = [f"# Kết quả đánh giá: `{os.path.basename(video)}`", "",
         f"- {m['n_frames']} frame, {f(m['duration_s'], '{:.1f}')} s, FPS ghi thực tế {f(m['capture_fps'], '{:.1f}')}, "
         f"thấy mặt {f(m['face_coverage_pct'], '{:.1f}')}% frame, hiệu chuẩn xong lúc {f(m['calibrated_at_s'], '{:.1f}')} s",
         "", "## 1. Mắt nhắm/mở theo frame", "",
         f"Bỏ {REACTION_S} s đầu mỗi đoạn (thời gian phản ứng), bỏ đoạn chớp mắt tự do/ngáp/quay đầu.", "",
         "| Phương pháp | Precision | Recall | F1 | Accuracy | n frame |", "|---|---|---|---|---|---|",
         f"| Hệ thống: EAR cá nhân hoá VÀ blendshape (cả 2 mắt) | {f(e1['precision'])} | {f(e1['recall'])} | {f(e1['f1'])} | {f(e1['accuracy'])} | {e1['n']} |",
         f"| Chỉ blendshape eyeBlink > 0.5 (MediaPipe) | {f(e2['precision'])} | {f(e2['recall'])} | {f(e2['f1'])} | {f(e2['accuracy'])} | {e2['n']} |",
         "", "## 2. Theo sự kiện (cảnh báo có kịp không)", "",
         "| Đoạn | Mong đợi | Bắt được | Trễ từ lúc có lời nhắc (s) |", "|---|---|---|---|"]
    for ev in m["events"]:
        L.append(f"| {ev['prompt']} | {ev['expect']} | {'✅' if ev['detected'] else '❌'} | {f(ev['delay_s'])} |")
    L += ["", f"- Tỉ lệ bắt sự kiện: **{f(100 * m['event_recall'], '{:.0f}')}%**; trễ TB buồn ngủ "
          f"**{f(m['drowsy_delay_mean_s'])} s** (gồm ngưỡng 1.0 s + phản ứng người), xao nhãng **{f(m['distract_delay_mean_s'])} s** (ngưỡng 2.0 s)",
          f"- Báo động giả: **{len(m['false_alarms'])}** lần trong {f(m['ok_time_s'], '{:.0f}')} s bình thường "
          f"= {f(m['false_alarms_per_min'])} lần/phút"]
    for fa in m["false_alarms"]:
        L.append(f"  - t={fa['t']:.1f}s {fa['state']} trong đoạn \"{fa['prompt']}\"")
    L += ["", "## 3. Thời gian và độ ổn định", "",
          f"- Độ trễ xử lý frame→quyết định: p50 **{f(m['latency_ms_p50'], '{:.1f}')} ms**, p95 {f(m['latency_ms_p95'], '{:.1f}')} ms "
          f"(riêng model p50 {f(m['infer_ms_p50'], '{:.1f}')} ms)",
          f"- Độ rung góc đầu giữa 2 frame liên tiếp khi ngồi yên (std của chênh lệch): yaw thô {f(m['yaw_jitter_raw_deg'])}° → Kalman {f(m['yaw_jitter_kf_deg'])}°; "
          f"pitch thô {f(m['pitch_jitter_raw_deg'])}° → Kalman {f(m['pitch_jitter_kf_deg'])}°",
          "", "## 4. Từng đoạn (dùng để tìm ca lỗi)", "",
          "| t (s) | Lời nhắc | Mong đợi | Trạng thái chính | Báo động | Thấy mặt % | EAR TB | % nhắm | \\|nhìn ngang\\| | pitch đầu | % không chắc | Đạt |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for s in m["segments"]:
        ok_ = {True: "✅", False: "❌", None: "–"}[s["pass"]]
        L.append(f"| {s['start']:.0f} | {s['prompt']} | {s['expect']} | {s['main_state']} | {s['alarms']} | "
                 f"{s['face_pct']:.0f} | {f(s['ear_mean'])} | {s['closed_pct']:.0f} | {f(s['yaw_rel'], '{:.0f}')} | "
                 f"{f(s['pitch_rel'], '{:+.0f}')} | {s['uncertain_pct']:.0f} | {ok_} |")
    L += ["", "![timeline](timeline.png)", ""]
    open(path, "w").write("\n".join(L))


def plot(rows, segs, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = np.array([r["t"] for r in rows])
    g = lambda k: np.array([r.get(k, np.nan) for r in rows], float)  # noqa: E731  (log cũ chưa có eye_yaw)
    fig, ax = plt.subplots(4, 1, figsize=(13, 9), sharex=True,
                           gridspec_kw={"height_ratios": [3, 2, 2, 0.8]})
    for s in segs:
        c = "#ffd6d6" if s["eye"] == "closed" else ("#ffe8cc" if s["attention"] == "away" else None)
        if c:
            for a in ax[:3]:
                a.axvspan(s["start"], s["end"], color=c, lw=0)
    ax[0].plot(t, g("ear"), lw=1, label="EAR")
    ax[0].plot(t, g("closed_thr"), "--", lw=1, color="#e0201b", label="ngưỡng nhắm (cá nhân hoá)")
    ax[0].plot(t, 0.4 * g("blink_bs"), lw=0.8, alpha=0.6, color="#7a4cc2", label="blendshape eyeBlink × 0.4")
    ax[0].set_ylabel("EAR"); ax[0].legend(loc="upper right", fontsize=8); ax[0].set_ylim(0, 0.45)
    ax[0].set_title("Nền đỏ = nhãn nhắm mắt, nền cam = nhãn nhìn đi chỗ khác")
    ax[1].plot(t, g("yaw_rel"), lw=1, label="hướng nhìn ngang lệch (đầu + mắt)")
    ax[1].plot(t, g("eye_yaw"), lw=0.8, alpha=0.7, label="góc mắt (mống mắt)")
    ax[1].plot(t, g("pitch_rel"), lw=1, label="pitch đầu lệch (Kalman)")
    ax[1].plot(t, g("yaw_raw") - np.nanmedian(g("yaw_raw")[:60]), lw=0.5, alpha=0.4, label="yaw đầu thô")
    for y in (30, -30, -20):
        ax[1].axhline(y, ls=":", color="gray", lw=0.8)
    ax[1].set_ylabel("độ"); ax[1].legend(loc="upper right", fontsize=8)
    ax[2].plot(t, g("latency_ms"), lw=0.8, color="#555", label="độ trễ xử lý (ms)")
    ax[2].plot(t, g("perclos") * 100, lw=1, color="#ffbe00", label="PERCLOS %")
    ax[2].legend(loc="upper right", fontsize=8)
    st = [r["state"] for r in rows]
    for k in range(len(t) - 1):
        ax[3].axvspan(t[k], t[k + 1], color=STATE_COLORS.get(st[k], "#fff"), lw=0)
    ax[3].set_yticks([]); ax[3].set_xlabel("thời gian (s)"); ax[3].set_ylabel("trạng thái")
    for s in segs:
        ax[3].axvline(s["start"], color="k", lw=0.4)
    handles = [plt.Rectangle((0, 0), 1, 1, color=c) for c in STATE_COLORS.values()]
    ax[3].legend(handles, STATE_COLORS.keys(), ncol=6, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.6))
    fig.tight_layout()
    fig.savefig(path, dpi=120)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    args = ap.parse_args()
    base = os.path.splitext(args.video)[0]
    out = os.path.join("reports", os.path.basename(base))
    os.makedirs(out, exist_ok=True)
    segs = load_labels(base)
    cap = cv2.VideoCapture(args.video)
    n, fps = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)), cap.get(cv2.CAP_PROP_FPS) or 30
    cap.release()
    rows = run_pipeline(args.video, load_times(base, n, fps), os.path.join(out, "log.csv"))
    m = evaluate(rows, segs)
    with open(os.path.join(out, "metrics.json"), "w") as fh:
        json.dump(m, fh, indent=2, ensure_ascii=False, default=float)
    write_markdown(m, os.path.join(out, "metrics.md"), args.video)
    plot(rows, segs, os.path.join(out, "timeline.png"))
    print(open(os.path.join(out, "metrics.md")).read())


if __name__ == "__main__":
    main()
