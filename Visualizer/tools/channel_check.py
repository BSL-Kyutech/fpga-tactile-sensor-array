#!/usr/bin/env python3
"""
Step through the 24 channels one at a time: the selected channel is shown big and red,
with a bar chart of all channels below.  Touch the hand to find where the channel is.

  python Visualizer/tools/channel_check.py [start_channel]

Keys: n / right = next channel, p / left = previous channel, b = re-capture baseline.
"""

import os
import sys

import matplotlib.pyplot as plt
import matplotlib.animation as animation
import serial

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from icepizeroo import (BAUD, BASELINE_SAMPLES, NUM_SENSORS,  # noqa: E402
                        find_active_port, find_packet, parse_packet)

SMOOTHING = 0.3

for _k in ("keymap.back", "keymap.forward"):   # free left / right / p / n
    plt.rcParams[_k] = []

if __name__ == "__main__":
    st = {"ch": int(sys.argv[1]) if len(sys.argv) > 1 else 0, "buf": bytearray(),
          "base": [0] * NUM_SENSORS, "acc": [0] * NUM_SENSORS, "cnt": 0, "ready": False,
          "shown": [0.0] * NUM_SENSORS, "peak": 0.0}

    port = find_active_port()
    if port is None:
        sys.exit("ERROR: No COM port is sending the expected data (header 0xAB, footer 0xFF).")
    ser = serial.Serial(port, BAUD, timeout=0.05)
    ser.reset_input_buffer()

    def rebase():
        st.update(acc=[0] * NUM_SENSORS, cnt=0, ready=False, peak=0.0)

    fig, (axt, axb) = plt.subplots(2, 1, figsize=(10, 7), gridspec_kw={"height_ratios": [1, 2]})
    fig.canvas.manager.set_window_title("Channel Check")
    axt.axis("off")
    big = axt.text(0.5, 0.6, "", ha="center", va="center", fontsize=44, weight="bold")
    sub = axt.text(0.5, 0.1, "", ha="center", va="center", fontsize=12, family="monospace")
    bars = axb.bar(range(NUM_SENSORS), [0] * NUM_SENSORS, color="0.7")
    axb.set_xticks(range(NUM_SENSORS), [f"S{i}" for i in range(NUM_SENSORS)], fontsize=8)
    axb.set_ylabel("count - baseline")

    def update(_):
        st["buf"].extend(ser.read(ser.in_waiting or 1))
        acc, n = [0] * NUM_SENSORS, 0
        while True:
            pkt, st["buf"] = find_packet(st["buf"])
            if pkt is None:
                break
            v = [x for _, x in parse_packet(pkt)]
            if not st["ready"]:
                st["acc"] = [a + b for a, b in zip(st["acc"], v)]
                st["cnt"] += 1
                if st["cnt"] >= BASELINE_SAMPLES:
                    st["base"] = [a // st["cnt"] for a in st["acc"]]
                    st["ready"] = True
                continue
            acc = [a + max(0, x - b) for a, x, b in zip(acc, v, st["base"])]
            n += 1
        ch = st["ch"]
        if not st["ready"]:
            big.set_text("baseline... hands off")
            return []
        s = st["shown"]
        if n:
            for i in range(NUM_SENSORS):
                s[i] += SMOOTHING * (acc[i] / n - s[i])
        st["peak"] = max(st["peak"], s[ch])
        top = max(range(NUM_SENSORS), key=lambda i: s[i])
        big.set_text(f"S{ch} = {s[ch]:.0f}")
        big.set_color("red" if s[ch] > 30 else "black")
        sub.set_text(f"peak S{ch} = {st['peak']:.0f}   strongest now: S{top} = {s[top]:.0f}\n"
                     "n/right = next   p/left = prev   b = baseline")
        for i, b in enumerate(bars):
            b.set_height(s[i])
            b.set_color("red" if i == ch else "0.7")
        axb.set_ylim(0, max(100, max(s) * 1.2))
        return []

    def on_key(e):
        if e.key in ("n", "right"):
            st["ch"] = (st["ch"] + 1) % NUM_SENSORS
            st["peak"] = 0.0
        elif e.key in ("p", "left"):
            st["ch"] = (st["ch"] - 1) % NUM_SENSORS
            st["peak"] = 0.0
        elif e.key == "b":
            rebase()

    fig.canvas.mpl_connect("key_press_event", on_key)
    ani = animation.FuncAnimation(fig, update, interval=30, blit=False, cache_frame_data=False)
    try:
        plt.show()
    finally:
        ser.close()
