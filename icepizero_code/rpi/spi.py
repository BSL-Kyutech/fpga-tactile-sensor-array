import threading
import board
import busio
import digitalio
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
from std_msgs.msg import Float32MultiArray, UInt8MultiArray, MultiArrayDimension, MultiArrayLayout

# ─── SPI Setup ────────────────────────────────────────────────────────────────
cs = digitalio.DigitalInOut(board.CE0)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

spi = busio.SPI(board.SCK, MISO=board.MISO, MOSI=board.MOSI)
while not spi.try_lock():
    pass
spi.configure(baudrate=3_000_000, phase=0, polarity=0)

# ─── Packet Definition ────────────────────────────────────────────────────────
PKT_LEN     = 62
SYNC_BYTE   = 0xAB
END_BYTE    = 0xFF
NUM_SENSORS = 20

def read_packet():
    buf = bytearray(PKT_LEN)
    cs.value = False
    spi.readinto(buf)
    cs.value = True

    if buf[0] != SYNC_BYTE or buf[PKT_LEN - 1] != END_BYTE:
        return None

    values   = []
    detected = []
    for i in range(NUM_SENSORS):
        det  = bool(buf[3 * i + 1] & 0x01)
        high = buf[3 * i + 2]
        low  = buf[3 * i + 3]
        values.append((high << 8) | low)
        detected.append(det)

    return values, detected

# ─── ROS2 Node ────────────────────────────────────────────────────────────────
class TouchPublisher(Node):
    def __init__(self):
        super().__init__("icepi_touch")

        # Best-effort, keep-last-1: suits high-rate sensor data.
        # Subscribers that need reliability should use a compatible QoS.
        qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.pub_values = self.create_publisher(
            Float32MultiArray,
            "/icepi/touch/values",
            qos,
        )
        self.pub_detected = self.create_publisher(
            UInt8MultiArray,
            "/icepi/touch/detected",
            qos,
        )

        # Pre-build message skeletons once — avoids allocation every frame
        dim = MultiArrayDimension(label="sensor", size=NUM_SENSORS, stride=NUM_SENSORS)
        layout = MultiArrayLayout(dim=[dim], data_offset=0)

        self._val_msg = Float32MultiArray(layout=layout, data=[0.0] * NUM_SENSORS)
        self._det_msg = UInt8MultiArray(layout=layout, data=[0]   * NUM_SENSORS)

        self.get_logger().info("TouchPublisher ready")

    def publish(self, values, detected):
        self._val_msg.data = [float(v) for v in values]
        self._det_msg.data = [int(d)   for d in detected]
        self.pub_values.publish(self._val_msg)
        self.pub_detected.publish(self._det_msg)


def ros_spin(node):
    """Runs in a daemon thread — exits automatically when main thread ends."""
    rclpy.spin(node)


# ─── ROS2 Init ────────────────────────────────────────────────────────────────
rclpy.init()
ros_node = TouchPublisher()

ros_thread = threading.Thread(target=ros_spin, args=(ros_node,), daemon=True)
ros_thread.start()

# ─── Plot Setup ───────────────────────────────────────────────────────────────
SENSOR_LABELS = [f"S{i}" for i in range(NUM_SENSORS)]
MAX_DISPLAY   = 2000

fig, (ax_bar, ax_line) = plt.subplots(2, 1, figsize=(14, 8))
fig.suptitle("IcePI Zero — 20 Touch Sensors", fontsize=13)

bars = ax_bar.bar(SENSOR_LABELS, [0] * NUM_SENSORS, color="steelblue")
ax_bar.set_ylim(0, MAX_DISPLAY)
ax_bar.set_ylabel("Capacitance Count")
ax_bar.set_title("Live Sensor Values")
ax_bar.axhline(y=100, color="red", linestyle="--", linewidth=0.8, label="Touch threshold (100)")
ax_bar.legend(loc="upper right", fontsize=8)

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
            f"IcePI Zero — 20 Touch Sensors  [bad packets: {bad_packet_count}]",
            fontsize=13,
        )
        return bars.patches + lines

    values, detected = result

    # ── Publish to ROS2 ───────────────────────────────────────────────
    ros_node.publish(values, detected)

    # ── Update bar chart ──────────────────────────────────────────────
    for bar, val, det in zip(bars, values, detected):
        bar.set_height(val)
        bar.set_color("tomato" if det else "steelblue")

    # ── Update rolling history ────────────────────────────────────────
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
    interval=50,
    blit=True,
    cache_frame_data=False,
)

plt.tight_layout()

try:
    plt.show()
finally:
    # Clean shutdown — order matters
    spi.unlock()
    ros_node.destroy_node()
    rclpy.shutdown()