"""
Screen recorder for a matplotlib figure, for syncing with a camera video afterwards.

Writes, per recording, into the output folder:
  <name>.mp4         the figure at a constant FPS (frames repeated if drawing was slow,
                     so video time == wall-clock time since the start)
  <name>_sensor.csv  every received packet: unix time, raw values S0..S23
  <name>.json        start / stop wall-clock time (ms), frames, fps, packets, baseline

Needs imageio-ffmpeg (pip install imageio-ffmpeg), which bundles ffmpeg.
"""

import csv
import json
import os
import time
from datetime import datetime

import numpy as np

FPS = 30


def default_outdir():
    return os.path.join(os.path.expanduser("~"), "Videos", "hand_heatmap")


def stamp(t):
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


class FigureRecorder:
    def __init__(self, fig, outdir=None, prefix="hand", fps=FPS, num_sensors=24):
        self.fig = fig
        self.outdir = outdir or default_outdir()
        self.prefix = prefix
        self.fps = fps
        self.num_sensors = num_sensors
        self.active = False
        fig.canvas.mpl_connect("draw_event", self._on_draw)

    # ── control ──
    def start(self, baseline=None):
        import imageio_ffmpeg

        os.makedirs(self.outdir, exist_ok=True)
        self.t_start = time.time()
        self.p_start = time.perf_counter()
        self.name = f"{self.prefix}_{datetime.fromtimestamp(self.t_start).strftime('%Y%m%d_%H%M%S')}"
        base = os.path.join(self.outdir, self.name)
        self.video_path = base + ".mp4"

        img = self._grab()
        self.h, self.w = img.shape[0] // 2 * 2, img.shape[1] // 2 * 2   # libx264 needs even sizes
        self.writer = imageio_ffmpeg.write_frames(
            self.video_path, (self.w, self.h), fps=self.fps, codec="libx264",
            pix_fmt_in="rgb24", quality=8, macro_block_size=1)
        self.writer.send(None)
        self.frames = 0
        self.packets = 0
        self.baseline = baseline

        self.csv_file = open(base + "_sensor.csv", "w", newline="")
        self.csv = csv.writer(self.csv_file)
        self.csv.writerow(["unix_time", "t_from_start"] + [f"S{i}" for i in range(self.num_sensors)])
        self.active = True
        self._write_frame(img)
        print(f"REC start {stamp(self.t_start)} -> {self.video_path}")

    def stop(self):
        if not self.active:
            return None
        self._on_draw(None)                  # pad up to the stop time
        self.active = False
        t_end = time.time()
        self.writer.close()
        self.csv_file.close()
        meta = {
            "video": os.path.basename(self.video_path),
            "sensor_csv": self.name + "_sensor.csv",
            "start_unix": self.t_start, "start_local": stamp(self.t_start),
            "end_unix": t_end, "end_local": stamp(t_end),
            "duration_s": round(t_end - self.t_start, 3),
            "fps": self.fps, "frames": self.frames, "size": [self.w, self.h],
            "packets": self.packets, "baseline": self.baseline,
            "note": "video frame k shows the screen at start_unix + k / fps",
        }
        with open(os.path.join(self.outdir, self.name + ".json"), "w") as f:
            json.dump(meta, f, indent=1)
        print(f"REC stop  {stamp(t_end)}  {meta['duration_s']} s, {self.frames} frames -> {self.video_path}")
        return self.video_path

    def toggle(self, baseline=None):
        if self.active:
            return self.stop()
        self.start(baseline)
        return None

    def elapsed(self):
        return time.perf_counter() - self.p_start if self.active else 0.0

    # ── data ──
    def log_packet(self, raw_vals, t=None):
        if self.active:
            t = time.time() if t is None else t
            self.csv.writerow([f"{t:.6f}", f"{t - self.t_start:.6f}"] + list(raw_vals))
            self.packets += 1

    # ── frames ──
    def _grab(self):
        return np.asarray(self.fig.canvas.buffer_rgba())[:, :, :3]

    def _write_frame(self, img):
        frame = np.zeros((self.h, self.w, 3), dtype=np.uint8)      # crop / pad if the window was resized
        hh, ww = min(self.h, img.shape[0]), min(self.w, img.shape[1])
        frame[:hh, :ww] = img[:hh, :ww]
        self.writer.send(frame.tobytes())
        self.frames += 1

    def _on_draw(self, _event):
        if not self.active:
            return
        due = int(self.elapsed() * self.fps) + 1 - self.frames
        if due <= 0:
            return
        img = self._grab()
        for _ in range(due):
            self._write_frame(img)
