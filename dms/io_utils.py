"""DỮ LIỆU: ghi log CSV từng frame, ghi video, phát âm thanh cảnh báo."""
import csv
import math
import os
import platform
import shutil
import subprocess
import sys
import time

import cv2

from .pipeline import LOG_FIELDS


class CSVLogger:
    def __init__(self, path: str, extra_fields=()):
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self.f = open(path, "w", newline="")
        self.fields = LOG_FIELDS + list(extra_fields)
        self.w = csv.DictWriter(self.f, fieldnames=self.fields, extrasaction="ignore")
        self.w.writeheader()
        self.path = path

    def write(self, row: dict):
        out = {}
        for k in self.fields:
            v = row.get(k, "")
            if isinstance(v, float):
                v = "" if math.isnan(v) else round(v, 4)
            out[k] = v
        self.w.writerow(out)

    def close(self):
        self.f.close()


class Alarm:
    """Âm thanh không chặn vòng lặp chính (chạy tiến trình con)."""

    SOUNDS = {"DROWSY": "/System/Library/Sounds/Sosumi.aiff", "DISTRACTED": "/System/Library/Sounds/Ping.aiff"}

    def __init__(self, enabled=True, cooldown_s=1.5):
        self.enabled = enabled
        self.cooldown = cooldown_s
        self.last = 0.0
        self.mac = platform.system() == "Darwin" and shutil.which("afplay")

    def trigger(self, kind: str):
        if not self.enabled or time.time() - self.last < self.cooldown:
            return
        self.last = time.time()
        sound = self.SOUNDS.get(kind)
        if self.mac and sound and os.path.exists(sound):
            subprocess.Popen(["afplay", sound], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()


def make_writer(path, fps, size):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    return cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, size)
