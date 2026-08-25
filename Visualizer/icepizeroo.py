#!/usr/bin/env python3
"""
Icepi Zero – 24-channel touch sensor live scrolling plot
with baseline correction (average & subtract)
Auto-detects the COM port that is sending valid packets.
"""

import serial
import serial.tools.list_ports
import collections
import sys
import time
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.widgets import Button  # not used, but kept for future

# ───────────────── CONFIG ─────────────────
BAUD = 921600
PKT_LEN = 74
HEADER = 0xAB
FOOTER = 0xFF
NUM_SENSORS = 24
HISTORY = 400

BASELINE_SAMPLES = 80  # how many packets to average for baseline (~0.5–1 s)

# How long to listen on each candidate port while searching
DETECT_TIMEOUT = 0.4   # seconds
# ──────────────────────────────────────────


def find_packet(buf: bytearray):
    while len(buf) >= PKT_LEN:
        try:
            idx = buf.index(HEADER)
        except ValueError:
            buf.clear()
            return None, buf
        if idx > 0:
            del buf[:idx]
        if len(buf) < PKT_LEN:
            return None, buf
        if buf[PKT_LEN - 1] == FOOTER:
            pkt = bytes(buf[:PKT_LEN])
            del buf[:PKT_LEN]
            return pkt, buf
        else:
            del buf[0]
    return None, buf


def parse_packet(pkt: bytes):
    sensors = []
    for i in range(NUM_SENSORS):
        base = 1 + 3 * i
        det = bool(pkt[base] & 0x01)
        val = (pkt[base + 1] << 8) | pkt[base + 2]
        sensors.append((det, val))
    return sensors


def port_is_sending_data(port_name: str) -> bool:
    """Open the port briefly and check whether valid packets appear."""
    try:
        ser = serial.Serial(port_name, BAUD, timeout=0.05)
        ser.reset_input_buffer()
    except (serial.SerialException, OSError, ValueError):
        return False

    buf = bytearray()
    deadline = time.time() + DETECT_TIMEOUT
    found = False

    try:
        while time.time() < deadline:
            data = ser.read(ser.in_waiting or 1)
            if data:
                buf.extend(data)
            while True:
                pkt, buf = find_packet(buf)
                if pkt is None:
                    break
                # We got at least one valid packet → this is the right port
                found = True
                break
            if found:
                break
            time.sleep(0.01)
    finally:
        ser.close()

    return found


def find_active_port():
    """
    Search for a COM port that is actually transmitting the expected packets.
    Checks:
      1. All ports reported by the OS
      2. COM0 … COM100 (in case some are missing from the OS list)
    Returns the first matching port name or None.
    """
    candidates = []

    # 1) Ports the OS currently knows about
    for info in serial.tools.list_ports.comports():
        candidates.append(info.device)

    # 2) Explicitly try COM0 … COM100 (Windows-style)
    for i in range(0, 101):
        name = f"COM{i}"
        if name not in candidates:
            candidates.append(name)

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            unique.append(c)

    print("Scanning for a port that is sending Icepi Zero packets …")
    for port in unique:
        print(f"  Trying {port} …", end="", flush=True)
        if port_is_sending_data(port):
            print(" → FOUND (valid packets)")
            return port
        print(" no")

    return None


if __name__ == "__main__":
    PORT = find_active_port()
    if PORT is None:
        print("ERROR: No COM port is sending the expected data (header 0xAB, footer 0xFF).")
        print("Make sure the device is connected and powered, then try again.")
        sys.exit(1)

    print(f"Using {PORT} @ {BAUD}")
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.05)
        ser.reset_input_buffer()
    except serial.SerialException as e:
        print(f"ERROR: {e}")
        sys.exit(1)

    buf = bytearray()

    # ---------- baseline storage ----------
    baseline = [0] * NUM_SENSORS
    baseline_ready = False
    baseline_acc = [0] * NUM_SENSORS
    baseline_cnt = 0

    def capture_baseline():
        """Reset and start collecting a new baseline"""
        global baseline_ready, baseline_acc, baseline_cnt
        baseline_ready = False
        baseline_acc = [0] * NUM_SENSORS
        baseline_cnt = 0
        print("Capturing new baseline – keep hands off the sensors…")

    # ── plot setup ──
    fig, ax = plt.subplots(figsize=(12, 6))
    ax.set_title("Icepi Zero – 24 Touch Sensors (baseline corrected)")
    ax.set_xlabel("Sample (newest on the right)")
    ax.set_ylabel("Count − baseline")
    ax.set_xlim(0, HISTORY - 1)
    ax.set_ylim(0, 100)
    ax.grid(True, alpha=0.3)

    colors = plt.cm.tab20.colors + plt.cm.tab20b.colors
    lines = []
    histories = [collections.deque([0] * HISTORY, maxlen=HISTORY)
                 for _ in range(NUM_SENSORS)]

    for i in range(NUM_SENSORS):
        (ln,) = ax.plot(range(HISTORY), list(histories[i]),
                        color=colors[i % len(colors)],
                        label=f"S{i}", linewidth=1.3)
        lines.append(ln)

    ax.legend(loc="upper right", ncol=4, fontsize="x-small")
    status_text = ax.text(0.01, 0.97, "", transform=ax.transAxes,
                          va="top", fontsize=9, family="monospace",
                          bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8))

    # start first baseline capture automatically
    capture_baseline()

    def update(_frame):
        global buf, baseline_ready, baseline_acc, baseline_cnt, baseline

        data = ser.read(ser.in_waiting or 1)
        if data:
            buf.extend(data)

        while True:
            pkt, buf = find_packet(buf)
            if pkt is None:
                break

            sensors = parse_packet(pkt)
            raw_vals = [v for _, v in sensors]

            # ----- baseline collection phase -----
            if not baseline_ready:
                for i, v in enumerate(raw_vals):
                    baseline_acc[i] += v
                baseline_cnt += 1

                if baseline_cnt >= BASELINE_SAMPLES:
                    for i in range(NUM_SENSORS):
                        baseline[i] = baseline_acc[i] // baseline_cnt
                    baseline_ready = True
                    print("Baseline captured:", baseline)
                # during capture just show zeros
                for i in range(NUM_SENSORS):
                    histories[i].append(0)
            else:
                # ----- normal operation: subtract baseline -----
                for i, v in enumerate(raw_vals):
                    corrected = max(0, v - baseline[i])  # never go negative
                    histories[i].append(corrected)

            # status line
            if baseline_ready:
                flags = "".join("█" if (v - baseline[i]) > 15 else "·"
                                for i, v in enumerate(raw_vals))
                status_text.set_text(f"Touch: {flags} (press 'b' to re-baseline)")
            else:
                status_text.set_text(f"Capturing baseline… {baseline_cnt}/{BASELINE_SAMPLES}")

        # update plot lines
        for i, ln in enumerate(lines):
            ln.set_ydata(list(histories[i]))

        # auto-scale Y
        all_vals = [v for h in histories for v in h]
        if all_vals:
            ymax = max(50, max(all_vals) * 1.3)
            ax.set_ylim(0, ymax)

        return lines + [status_text]

    # ----- key press handler for re-baselining -----
    def on_key(event):
        if event.key == 'b':
            capture_baseline()

    fig.canvas.mpl_connect('key_press_event', on_key)

    ani = animation.FuncAnimation(fig, update, interval=30,
                                  blit=False, cache_frame_data=False)

    print("Live plot running")
    print(" - Keep hands off for the first second (baseline capture)")
    print(" - Press 'b' any time to re-capture baseline")
    print(" - Close window to quit")
    try:
        plt.show()
    except KeyboardInterrupt:
        pass
    finally:
        ser.close()
        print("Closed.")