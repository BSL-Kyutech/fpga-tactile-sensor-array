#!/usr/bin/env python3
"""
Force-scale (gain) calibration: press every taxel with the same force, 2-3 times each.

Each press is attributed to the channel that responded most, and its plateau value
(mean of the upper half of the press) is recorded.  The hand shows progress:
grey = no press yet, light/dark green = 1 / 2+ presses, label = presses and mean value.

"Save gains" writes gain = (median of all channels) / (median press value of the channel)
to each taxel in hand_layout.json (previous file kept as .bak); hand_heatmap.py then
multiplies by it, so equal force shows as an equal value.
Press values are also kept in gain_events.json, so a later run continues where this one stopped.

Keys: u = undo last press, b = re-capture baseline, w = save gains
"""

import json
import os
import shutil
import statistics
import sys
import time

import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Polygon
from matplotlib.widgets import Button
import matplotlib.patheffects as pe
import serial

from icepizeroo import (BAUD, BASELINE_SAMPLES, NUM_SENSORS,
                        find_active_port, find_packet, parse_packet)

HERE = os.path.dirname(os.path.abspath(__file__))
LAYOUT_FILE = os.path.join(HERE, "hand_layout.json")
EVENTS_FILE = os.path.join(HERE, "gain_events.json")
TH_ON = 10              # counts above baseline that start a press
TH_OFF = 5              # ... and end it
MIN_PRESS_SEC = 0.3
SMOOTHING = 0.3         # EMA weight of each new frame
DRIFT_FOLLOW = 0.01     # per-frame baseline follow while idle

COL_NONE = "0.88"
COL_ONE = "#b7e4a7"
COL_MANY = "#3a9a3a"

for _k in ("keymap.save", "keymap.back"):
    plt.rcParams[_k] = []


def compute_gains(events):
    per_ch = {}
    for e in events:
        per_ch.setdefault(e["ch"], []).append(e["plateau"])
    med = {c: statistics.median(v) for c, v in per_ch.items() if v}
    if not med:
        return {}, None
    ref = statistics.median(med.values())
    return {c: ref / m for c, m in med.items() if m > 0}, ref


if __name__ == "__main__":
    with open(LAYOUT_FILE) as f:
        layout = json.load(f)
    taxels = layout["taxels"]
    ch_to_taxel = {t["channel"]: k for k, t in enumerate(taxels) if t["channel"] is not None}

    events = []
    if os.path.exists(EVENTS_FILE):
        with open(EVENTS_FILE) as f:
            events = json.load(f)["events"]
        print(f"Loaded {len(events)} earlier presses from {EVENTS_FILE}")

    PORT = find_active_port()
    if PORT is None:
        print("ERROR: No COM port is sending the expected data (header 0xAB, footer 0xFF).")
        sys.exit(1)
    print(f"Using {PORT} @ {BAUD}")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.05)
        ser.reset_input_buffer()
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    buf = bytearray()
    baseline = [0.0] * NUM_SENSORS
    baseline_ready = False
    baseline_acc = [0] * NUM_SENSORS
    baseline_cnt = 0
    shown = [0.0] * NUM_SENSORS
    press = {"start": None, "frames": []}
    msg = {"text": ""}

    def capture_baseline():
        global baseline_ready, baseline_acc, baseline_cnt
        baseline_ready = False
        baseline_acc = [0] * NUM_SENSORS
        baseline_cnt = 0
        press["start"] = None
        print("Capturing new baseline - keep hands off the sensors...")

    def save_events():
        with open(EVENTS_FILE, "w") as f:
            json.dump({"events": events}, f, indent=1)

    # ── plot setup ──
    fig = plt.figure(figsize=(10, 7))
    fig.canvas.manager.set_window_title("Gain Calibration")
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.82])
    ax.set_aspect("equal")
    ax.axis("off")
    for pts in layout["outline"]:
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="0.3", linewidth=1.0)

    taxel_patches, labels = [], []
    for t in taxels:
        ps = []
        for pts in t["polygons"]:
            p = Polygon(pts, closed=True, facecolor=COL_NONE, edgecolor="0.2", linewidth=0.6,
                        hatch="//" if t["channel"] is None else None)
            ax.add_patch(p)
            ps.append(p)
        taxel_patches.append(ps)
        pts = max(t["polygons"], key=len)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        labels.append(ax.text(cx, cy, "", ha="center", va="center", fontsize=7, weight="bold",
                              path_effects=[pe.withStroke(linewidth=2.5, foreground="white")]))
    ax.autoscale_view()
    title = ax.set_title("", fontsize=12)
    status_text = ax.text(0.01, 0.99, "", transform=ax.transAxes, va="top",
                          fontsize=9, family="monospace",
                          bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

    def redraw(active_ch=None):
        per_ch = {}
        for e in events:
            per_ch.setdefault(e["ch"], []).append(e["plateau"])
        for k, (t, ps, lab) in enumerate(zip(taxels, taxel_patches, labels)):
            c = t["channel"]
            vals = per_ch.get(c, []) if c is not None else []
            col = COL_NONE if not vals else COL_ONE if len(vals) == 1 else COL_MANY
            for p in ps:
                p.set_facecolor(col)
                p.set_edgecolor("tab:orange" if c is not None and c == active_ch else "0.2")
                p.set_linewidth(3.0 if c is not None and c == active_ch else 0.6)
            if c is None:
                lab.set_text("-")
            elif vals:
                lab.set_text(f"S{c}\n{len(vals)}x {statistics.mean(vals):.0f}")
            else:
                lab.set_text(f"S{c}")
        done = sum(1 for t in taxels if t["channel"] in per_ch)
        n_mapped = sum(1 for t in taxels if t["channel"] is not None)
        title.set_text(f"Press each taxel with the same force (2-3 times)   "
                       f"{done}/{n_mapped} taxels, {len(events)} presses")

    def record(frames, held):
        sums = [sum(f[i] for f in frames) for i in range(NUM_SENSORS)]
        ch = max(range(NUM_SENSORS), key=lambda i: sums[i])
        vals = sorted(f[ch] for f in frames)
        upper = vals[len(vals) // 2:]
        plateau = sum(upper) / len(upper)
        second = sorted(range(NUM_SENSORS), key=lambda i: -sums[i])[1]
        ev = {"ch": ch, "plateau": round(plateau, 1), "peak": round(vals[-1], 1),
              "sec": round(held, 2), "second": second,
              "second_ratio": round(sums[second] / sums[ch], 2) if sums[ch] else 0,
              "time": time.strftime("%H:%M:%S")}
        events.append(ev)
        save_events()
        where = taxels[ch_to_taxel[ch]]["name"] if ch in ch_to_taxel else "not on hand"
        msg["text"] = f"last: S{ch} ({where}) plateau {plateau:.0f}"
        print(json.dumps(ev))

    def undo(_=None):
        if events:
            e = events.pop()
            save_events()
            msg["text"] = f"undone: S{e['ch']} plateau {e['plateau']:.0f}"
            redraw()

    def save_gains(_=None):
        gains, ref = compute_gains(events)
        if not gains:
            msg["text"] = "nothing to save yet"
            return
        shutil.copyfile(LAYOUT_FILE, LAYOUT_FILE + ".bak")
        for t in taxels:
            g = gains.get(t["channel"])
            t["gain"] = round(g, 4) if g is not None else None
        layout["gain_note"] = (f"gain = {ref:.1f} / median press value of the channel; equal force "
                               f"-> equal displayed value. Measured with hand_gain_calibrate.py on "
                               f"{time.strftime('%Y-%m-%d')} from {len(events)} presses.")
        with open(LAYOUT_FILE, "w") as f:
            json.dump(layout, f, separators=(",", ":"))
        msg["text"] = f"saved gains for {len(gains)} channels (reference {ref:.0f})"
        print("Saved gains:", {f"S{c}": round(g, 3) for c, g in sorted(gains.items())})

    buttons = []
    for x, label, cb in [(0.10, "Undo last (u)", undo),
                         (0.30, "Baseline (b)", lambda _: capture_baseline()),
                         (0.50, "Save gains (w)", save_gains)]:
        b = Button(fig.add_axes([x, 0.92, 0.17, 0.06]), label)
        b.on_clicked(cb)
        buttons.append(b)

    capture_baseline()
    redraw()

    def update(_frame):
        global buf, baseline_ready, baseline_acc, baseline_cnt, baseline

        data = ser.read(ser.in_waiting or 1)
        if data:
            buf.extend(data)
        acc = [0.0] * NUM_SENSORS
        raw_acc = [0] * NUM_SENSORS
        n = 0
        while True:
            pkt, buf = find_packet(buf)
            if pkt is None:
                break
            raw_vals = [v for _, v in parse_packet(pkt)]
            if not baseline_ready:
                for i, v in enumerate(raw_vals):
                    baseline_acc[i] += v
                baseline_cnt += 1
                if baseline_cnt >= BASELINE_SAMPLES:
                    baseline = [a / baseline_cnt for a in baseline_acc]
                    baseline_ready = True
                continue
            for i, v in enumerate(raw_vals):
                acc[i] += max(0.0, v - baseline[i])
                raw_acc[i] += v
            n += 1

        if not baseline_ready:
            status_text.set_text(f"Capturing baseline... {baseline_cnt}/{BASELINE_SAMPLES} - hands off")
            return []
        if not n:
            return []
        for i in range(NUM_SENSORS):
            shown[i] += SMOOTHING * (acc[i] / n - shown[i])
        top = max(range(NUM_SENSORS), key=lambda i: shown[i])

        if press["start"] is None:
            if shown[top] > TH_ON:
                press["start"] = time.time()
                press["frames"] = []
            else:
                for i in range(NUM_SENSORS):
                    baseline[i] += DRIFT_FOLLOW * (raw_acc[i] / n - baseline[i])
        if press["start"] is not None:
            press["frames"].append(list(shown))
            if shown[top] < TH_OFF:
                held = time.time() - press["start"]
                frames = press["frames"]
                press["start"] = None
                if held >= MIN_PRESS_SEC:
                    record(frames, held)
                    redraw()

        pressing = press["start"] is not None
        redraw(active_ch=top if pressing else None)
        status_text.set_text(
            f"now: S{top} = {shown[top]:5.0f}  {'PRESS' if pressing else '     '}\n{msg['text']}")
        return []

    def on_key(event):
        if event.key == "u":
            undo()
        elif event.key == "b":
            capture_baseline()
        elif event.key == "w":
            save_gains()

    fig.canvas.mpl_connect("key_press_event", on_key)
    ani = animation.FuncAnimation(fig, update, interval=30,
                                  blit=False, cache_frame_data=False)

    print("Gain calibration running - keep hands off for the first second (baseline capture)")
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("Closed.")
