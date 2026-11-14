#!/usr/bin/env python3
"""
Find which channel (S0..S23) each hand taxel is wired to, and save it to hand_layout.json.

The highlighted (orange) taxel is the one to touch.  Press it for about a second and
release: the channel that responded most is assigned and the next taxel is highlighted.
Click any taxel to make it the current one (to do them in any order or redo one).
Use the buttons (or keys) to skip a taxel that does not respond.  When every taxel is
done or skipped the mapping is written to hand_layout.json (previous file kept as .bak).

While nobody is touching, the baseline slowly follows the raw values, so channels
that drift do not trigger a false touch.

Keys (on the plot window):
  s          skip this taxel (no channel)
  backspace  go back to the previous taxel
  b          re-capture baseline (keep hands off)
  + / -      raise / lower the touch threshold
  w          save now (taxels not done yet get no channel)
"""

import json
import os
import shutil
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

LAYOUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hand_layout.json")
THRESHOLD_START = 10    # counts above baseline that count as a touch
THRESHOLD_STEP = 5
MIN_TOUCH_SEC = 0.3     # shorter presses are ignored
SMOOTHING = 0.3         # EMA weight of each new frame
DRIFT_FOLLOW = 0.01     # per-frame weight of the baseline following raw values while idle

COL_TODO = "0.9"
COL_NOW = "tab:orange"
COL_DONE = "tab:green"
COL_SKIP = "0.6"

TODO, DONE, SKIP = "todo", "done", "skip"

# free the keys used below from matplotlib's default shortcuts (s = save figure, backspace = back)
for _k in ("keymap.save", "keymap.back"):
    plt.rcParams[_k] = []


def save(layout, result):
    shutil.copyfile(LAYOUT_FILE, LAYOUT_FILE + ".bak")
    for t, ch in zip(layout["taxels"], result):
        t["channel"] = ch
    layout["mapping_note"] = ("channel = index into the 24 sensor values (S0..S23); null = not connected. "
                              "Measured by touch with hand_calibrate.py on " + time.strftime("%Y-%m-%d") +
                              "; replace with the mapping from the firmware pin constraints (.lpf) when available.")
    with open(LAYOUT_FILE, "w") as f:
        json.dump(layout, f, separators=(",", ":"))


if __name__ == "__main__":
    with open(LAYOUT_FILE) as f:
        layout = json.load(f)
    taxels = layout["taxels"]

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
    threshold = THRESHOLD_START

    result = [None] * len(taxels)     # assigned channel per taxel
    status = [TODO] * len(taxels)
    state = {"i": 0, "prev": [], "touch_start": None, "touch_sum": [0.0] * NUM_SENSORS, "saved": False}

    def capture_baseline():
        global baseline_ready, baseline_acc, baseline_cnt
        baseline_ready = False
        baseline_acc = [0] * NUM_SENSORS
        baseline_cnt = 0
        state["touch_start"] = None
        print("Capturing new baseline - keep hands off the sensors...")

    # ── plot setup ──
    fig = plt.figure(figsize=(10, 7))
    fig.canvas.manager.set_window_title("Hand Calibration")
    ax = fig.add_axes([0.02, 0.02, 0.96, 0.82])
    ax.set_aspect("equal")
    ax.axis("off")
    for pts in layout["outline"]:
        xs, ys = zip(*pts)
        ax.plot(xs, ys, color="0.3", linewidth=1.0)

    taxel_patches, labels = [], []
    patch_owner = {}
    for k, t in enumerate(taxels):
        ps = []
        for pts in t["polygons"]:
            p = Polygon(pts, closed=True, facecolor=COL_TODO, edgecolor="0.2", linewidth=0.6)
            ax.add_patch(p)
            ps.append(p)
            patch_owner[p] = k
        taxel_patches.append(ps)
        pts = max(t["polygons"], key=len)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        labels.append(ax.text(cx, cy, "", ha="center", va="center", fontsize=9, weight="bold",
                              path_effects=[pe.withStroke(linewidth=2.5, foreground="white")]))
    ax.autoscale_view()

    title = ax.set_title("", fontsize=13)
    status_text = ax.text(0.01, 0.99, "", transform=ax.transAxes, va="top",
                          fontsize=9, family="monospace",
                          bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

    def redraw():
        i = state["i"]
        for k, (ps, lab) in enumerate(zip(taxel_patches, labels)):
            if k == i:
                col, lw, txt = COL_NOW, 2.5, "?"
            elif status[k] == DONE:
                col, lw, txt = COL_DONE, 0.6, f"S{result[k]}"
            elif status[k] == SKIP:
                col, lw, txt = COL_SKIP, 0.6, "-"
            else:
                col, lw, txt = COL_TODO, 0.6, ""
            for p in ps:
                p.set_facecolor(col)
                p.set_linewidth(lw)
            lab.set_text(txt)
        n_done = sum(s != TODO for s in status)
        if i is not None:
            title.set_text(f"Touch: {taxels[i]['name']}   ({n_done}/{len(taxels)} done)")
        else:
            used = [c for c in result if c is not None]
            dup = sorted({c for c in used if used.count(c) > 1})
            msg = "All done - saved to hand_layout.json"
            if dup:
                msg += "  (WARNING: duplicate " + ", ".join(f"S{c}" for c in dup) + ")"
            title.set_text(msg)
        fig.canvas.draw_idle()

    def write_now():
        save(layout, result)
        state["saved"] = True
        print("Saved mapping:")
        for t, ch, st in zip(taxels, result, status):
            print(f"  {t['name']:18s} {'S' + str(ch) if ch is not None else '-'}  ({st})")
        unused = [c for c in range(NUM_SENSORS) if c not in result]
        print("Channels not on the hand:", " ".join(f"S{c}" for c in unused))

    def next_todo(start):
        for k in list(range(start + 1, len(taxels))) + list(range(0, start + 1)):
            if status[k] == TODO:
                return k
        return None

    def go_to(k):
        if state["i"] is not None:
            state["prev"].append(state["i"])
        state["i"] = k
        state["touch_start"] = None
        redraw()

    def assign(ch):
        i = state["i"]
        result[i] = ch
        status[i] = DONE if ch is not None else SKIP
        print(f"{taxels[i]['name']:18s} -> {'S' + str(ch) if ch is not None else 'skipped'}")
        go_to(next_todo(i))
        if state["i"] is None:
            write_now()
            redraw()

    def do_skip(_=None):
        if state["i"] is not None:
            assign(None)

    def do_back(_=None):
        if state["prev"]:
            k = state["prev"].pop()
            result[k] = None
            status[k] = TODO
            state["i"] = k
            state["touch_start"] = None
            redraw()

    def do_threshold(delta):
        global threshold
        threshold = max(THRESHOLD_STEP, threshold + delta)

    def do_save(_=None):
        write_now()
        title.set_text(title.get_text() + "   [saved]")
        fig.canvas.draw_idle()

    capture_baseline()
    redraw()

    # ── buttons (top row, so they stay visible on small screens) ──
    buttons = []
    for x, label, cb in [(0.05, "Skip (s)", do_skip),
                         (0.20, "Back (bksp)", do_back),
                         (0.35, "Baseline (b)", lambda _: capture_baseline()),
                         (0.50, "Threshold - (-)", lambda _: do_threshold(-THRESHOLD_STEP)),
                         (0.65, "Threshold + (+)", lambda _: do_threshold(THRESHOLD_STEP)),
                         (0.80, "Save now (w)", do_save)]:
        b = Button(fig.add_axes([x, 0.92, 0.14, 0.06]), label)
        b.on_clicked(cb)
        buttons.append(b)

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
                    print("Baseline captured:", [round(b) for b in baseline])
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
        touching = shown[top] > threshold
        idle = state["touch_start"] is None and shown[top] < threshold / 2
        if idle:
            # follow slow drift while nobody touches
            for i in range(NUM_SENSORS):
                baseline[i] += DRIFT_FOLLOW * (raw_acc[i] / n - baseline[i])

        if state["i"] is not None:
            if touching:
                if state["touch_start"] is None:
                    state["touch_start"] = time.time()
                    state["touch_sum"] = [0.0] * NUM_SENSORS
                for i in range(NUM_SENSORS):
                    state["touch_sum"][i] += shown[i]
            elif state["touch_start"] is not None and shown[top] < threshold / 2:
                held = time.time() - state["touch_start"]
                if held >= MIN_TOUCH_SEC:
                    s = state["touch_sum"]
                    assign(max(range(NUM_SENSORS), key=lambda i: s[i]))
                else:
                    state["touch_start"] = None

        status_text.set_text(
            f"now: S{top} = {shown[top]:5.0f}   threshold {threshold}  "
            f"{'TOUCH' if touching else '     '}\n"
            "click a taxel to select it")
        return []

    def on_key(event):
        if event.key == "b":
            capture_baseline()
        elif event.key == "s":
            do_skip()
        elif event.key == "backspace":
            do_back()
        elif event.key in ("+", "="):
            do_threshold(THRESHOLD_STEP)
        elif event.key == "-":
            do_threshold(-THRESHOLD_STEP)
        elif event.key == "w":
            do_save()

    def on_click(event):
        if event.inaxes is not ax:
            return
        for p, k in patch_owner.items():
            if p.contains_point((event.x, event.y)):
                if k != state["i"]:
                    status[k] = TODO
                    result[k] = None
                    go_to(k)
                return

    fig.canvas.mpl_connect("key_press_event", on_key)
    fig.canvas.mpl_connect("button_press_event", on_click)
    ani = animation.FuncAnimation(fig, update, interval=30,
                                  blit=False, cache_frame_data=False)

    print("Calibration running - keep hands off for the first second (baseline capture)")
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("Closed.")
