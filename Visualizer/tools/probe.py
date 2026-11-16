#!/usr/bin/env python3
"""
Check that the Icepi Zero is connected and sending packets, without opening a plot.

Finds the FTDI port (VID:PID 0403:6015), reads it for 1.5 s at 921600 baud and counts
74-byte packets (0xAB ... 0xFF).  Also checks that matplotlib can be imported.

Exit code: 0 = packets OK, 2 = device not found, 3 = port cannot be opened (in use?),
           4 = port opens but no packets.
"""

import sys
import time

import matplotlib  # noqa: F401  (import check only)
import serial
import serial.tools.list_ports

BAUD = 921600
PKT_LEN = 74

ports = [p for p in serial.tools.list_ports.comports() if p.vid == 0x0403 and p.pid == 0x6015]
print("all ports:", [(p.device, p.description) for p in serial.tools.list_ports.comports()])
if not ports:
    print("NG: Icepi Zero (0403:6015) not found")
    sys.exit(2)
port = ports[0].device
try:
    s = serial.Serial(port, BAUD, timeout=0.1)
except serial.SerialException as e:
    print(f"NG: cannot open {port}: {e}")
    sys.exit(3)
s.reset_input_buffer()
buf = bytearray()
t = time.time()
while time.time() - t < 1.5:
    buf += s.read(4096)
s.close()
n = sum(1 for i in range(len(buf) - PKT_LEN + 1) if buf[i] == 0xAB and buf[i + PKT_LEN - 1] == 0xFF)
print(f"{port}: {len(buf)} bytes, {n} packets in 1.5 s")
sys.exit(0 if n > 0 else 4)
