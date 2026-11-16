#!/usr/bin/env python3
"""
Render hand_heatmap.py to a PNG with a fake serial port (no board needed), to check
the drawing after changing the layout, gains or the viewer itself.

  python Visualizer/tools/sim_heatmap.py out.png [hand_heatmap options, e.g. --raw]

Fake data: S3 +250, S10 +120, S7 slowly varying, S21 (not on the hand) +60.
"""

import gc
import math
import os
import runpy
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.animation import FuncAnimation  # noqa: E402

VIS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, VIS_DIR)
import serial  # noqa: E402
import icepizeroo  # noqa: E402


class FakeSerial:
    def __init__(self, *a, **k):
        self.n = 0

    def reset_input_buffer(self):
        pass

    @property
    def in_waiting(self):
        return 74 * 40

    def read(self, size):
        out = bytearray()
        for _ in range(size // 74):
            self.n += 1
            vals = [1000 + (self.n % 3)] * 24
            if self.n > 100:
                vals[3] += 250
                vals[10] += 120
                vals[21] += 60
                vals[7] += 30 * (1 + math.sin(self.n / 50))
            pkt = bytearray([0xAB])
            for v in vals:
                v = int(v)
                pkt += bytes([1, v >> 8, v & 0xFF])
            pkt.append(0xFF)
            out += pkt
        return bytes(out)

    def close(self):
        pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out_png = sys.argv[1]
    serial.Serial = FakeSerial
    icepizeroo.find_active_port = lambda: "SIM"

    def fake_show():
        anim = [o for o in gc.get_objects() if isinstance(o, FuncAnimation)][0]
        for i in range(30):
            anim._func(i)
        plt.gcf().savefig(out_png, dpi=90)
        print("wrote", out_png)

    plt.show = fake_show
    sys.argv = ["hand_heatmap.py"] + sys.argv[2:]
    runpy.run_path(os.path.join(VIS_DIR, "hand_heatmap.py"), run_name="__main__")
