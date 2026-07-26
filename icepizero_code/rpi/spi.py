import board
import busio
import digitalio
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

# ─── SPI Setup ────────────────────────────────────────────────────────────────
cs = digitalio.DigitalInOut(board.CE0)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

spi = busio.SPI(board.SCK, MISO=board.MISO, MOSI=board.MOSI)
while not spi.try_lock():
    pass
spi.configure(baudrate=3_000_000, phase=0, polarity=0)

# ─── Packet Definition ────────────────────────────────────────────────────────
# 62 bytes:
#   [0]       = 0xAB  sync
#   [3*i+1]   = touch_detected[i]   i = 0..19
#   [3*i+2]   = value[i] high byte
#   [3*i+3]   = value[i] low byte
#   [61]      = 0xFF  end marker

PKT_LEN    = 62
SYNC_BYTE  = 0xAB
END_BYTE   = 0xFF
NUM_SENSORS = 20

# ─── Packet Reader ────────────────────────────────────────────────────────────
def read_packet():
    """
    Returns (values, detected) tuple:
      values   — list of 20 ints (raw capacitance count)
      detected — list of 20 bools
    Returns None if packet is malformed.
    """
    buf = bytearray(PKT_LEN)
    cs.value = False
    spi.readinto(buf)
    cs.value = True

    if buf[0] != SYNC_BYTE or buf[PKT_LEN - 1] != END_BYTE:
        return None  # drop corrupt packet

    values   = []
    detected = []
    for i in range(NUM_SENSORS):
        det  = bool(buf[3 * i + 1] & 0x01)
        high = buf[3 * i + 2]
        low  = buf[3 * i + 3]
        val  = (high << 8) | low
        detected.append(det)
        values.append(val)

    return values, detected

# ─── Plot Setup ───────────────────────────────────────────────────────────────
SENSOR_LABELS = [f"S{i}" for i in range(NUM_SENSORS)]
MAX_DISPLAY   = 2000   # match MAX_COUNT in your HDL

fig, (ax_bar, ax_line) = plt.subplots(2, 1, figsize=(14, 8))
fig.suptitle("IcePI Zero — 20 Capacitive Touch Sensors", fontsize=13)

# --- Bar chart (current snapshot) ---
bars = ax_bar.bar(SENSOR_LABELS, [0] * NUM_SENSORS, color="steelblue")
ax_bar.set_ylim(0, MAX_DISPLAY)
ax_bar.set_ylabel("Capacitance Count")
ax_bar.set_title("Live Sensor Values")
ax_bar.axhline(y=100, color="red", linestyle="--", linewidth=0.8, label="Touch threshold (100)")
ax_bar.legend(loc="upper right", fontsize=8)

# --- Line chart (rolling history) ---
HISTORY_LEN = 200
history = np.zeros((NUM_SENSORS, HISTORY_LEN))
lines   = [ax_line.plot([], [], linewidth=0.8, label=f"S{i}")[0]
           for i in range(NUM_SENSORS)]
ax_line.set_xlim(0, HISTORY_LEN)
ax_line.set_ylim(0, MAX_DISPLAY)
ax_line.set_ylabel("Capacitance Count")
ax_line.set_xlabel("Samples")
ax_line.set_title("Rolling History")
ax_line.legend(loc="upper right", fontsize=6, ncol=4)

bad_packet_count = 0

# ─── Animation Callback ───────────────────────────────────────────────────────
def update(_frame):
    global history, bad_packet_count

    result = read_packet()

    if result is None:
        bad_packet_count += 1
        fig.suptitle(
            f"IcePI Zero — 20 Capacitive Touch Sensors  "
            f"[bad packets: {bad_packet_count}]",
            fontsize=13
        )
        return bars.patches + lines

    values, detected = result

    # Update bar chart
    for i, (bar, val, det) in enumerate(zip(bars, values, detected)):
        bar.set_height(val)
        bar.set_color("tomato" if det else "steelblue")

    # Update rolling history
    history = np.roll(history, -1, axis=1)
    for i, val in enumerate(values):
        history[i, -1] = val

    x = np.arange(HISTORY_LEN)
    for i, line in enumerate(lines):
        line.set_data(x, history[i])

    return bars.patches + lines

# ─── Run ──────────────────────────────────────────────────────────────────────
ani = animation.FuncAnimation(
    fig,
    update,
    interval=50,      # ms between frames — increase if SPI is too slow
    blit=True,
    cache_frame_data=False
)

plt.tight_layout()
plt.show()

# Cleanup
spi.unlock()