#!/usr/bin/env python3
"""
Log which channels move while you touch the hand (no plot).  Useful to find dead,
stuck or shorted channels: every 0.5 s it prints the channels whose mean
|value - baseline| exceeds the threshold, and at the end the min/max change per channel.

  python Visualizer/tools/watch_channels.py [--seconds 60] [--out watch.json]

Keep hands off for the first 2 s (baseline).  Ctrl+C stops early.
Two channels that always move together by the same amount are probably shorted.
"""

import argparse
import json
import os
import sys
import time

import serial

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from icepizeroo import BAUD, NUM_SENSORS, find_active_port, find_packet, parse_packet  # noqa: E402

THRESHOLD = 8
BASELINE_SEC = 2.0

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--out", help="write baseline and per-channel min/max change as JSON")
    args = ap.parse_args()

    port = find_active_port()
    if port is None:
        sys.exit("ERROR: No COM port is sending the expected data (header 0xAB, footer 0xFF).")
    s = serial.Serial(port, BAUD, timeout=0.05)
    s.reset_input_buffer()

    buf = bytearray()
    acc, n, base = [0] * NUM_SENSORS, 0, None
    lo, hi = [0.0] * NUM_SENSORS, [0.0] * NUM_SENSORS
    win, t_win, t0 = [], time.time(), time.time()
    print("baseline - hands off", flush=True)
    try:
        while time.time() - t0 < args.seconds:
            buf += s.read(4096)
            while True:
                pkt, buf = find_packet(buf)
                if pkt is None:
                    break
                v = [x for _, x in parse_packet(pkt)]
                if base is None:
                    acc = [a + b for a, b in zip(acc, v)]
                    n += 1
                    if time.time() - t0 > BASELINE_SEC:
                        base = [a / n for a in acc]
                        print("READY - baseline:", [round(b) for b in base], flush=True)
                    continue
                d = [x - b for x, b in zip(v, base)]
                win.append(d)
                for i in range(NUM_SENSORS):
                    lo[i] = min(lo[i], d[i])
                    hi[i] = max(hi[i], d[i])
            if base is not None and win and time.time() - t_win >= 0.5:
                avg = [sum(r[i] for r in win) / len(win) for i in range(NUM_SENSORS)]
                hits = {f"S{i}": round(a) for i, a in enumerate(avg) if abs(a) > THRESHOLD}
                if hits:
                    print(f"{time.time() - t0:5.1f}s", hits, flush=True)
                win, t_win = [], time.time()
    except KeyboardInterrupt:
        pass
    finally:
        s.close()

    summary = {f"S{i}": [round(lo[i]), round(hi[i])] for i in range(NUM_SENSORS)}
    print("min/max change per channel:", " ".join(f"{k}:{a}/{b}" for k, (a, b) in summary.items()))
    if args.out:
        with open(args.out, "w") as f:
            json.dump({"baseline": base, "range": summary}, f)
