import serial
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np

SERIAL_PORT = 'COM8'
BAUD_RATE = 2000000
NUM_SENSORS = 100
WINDOW_SIZE = 500
HEADER_BYTE = 252

# RAW data — no baseline subtraction, no smoothing
data_array = np.zeros((NUM_SENSORS, WINDOW_SIZE), dtype=np.float32)
is_receiving = False

def read_serial_data():
    global is_receiving
    import threading
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=0.05)
    ser.reset_input_buffer()
    buffer = bytearray()
    
    while True:
        if ser.in_waiting:
            buffer.extend(ser.read(ser.in_waiting))
        
        while len(buffer) >= NUM_SENSORS + 1:
            if buffer[0] == HEADER_BYTE:
                is_receiving = True
                # RAW VALUES — no subtraction
                packet_data = np.frombuffer(
                    buffer[1:NUM_SENSORS+1], 
                    dtype=np.uint8
                ).astype(np.float32)
                
                data_array[:, :-1] = data_array[:, 1:]
                data_array[:, -1] = packet_data
                del buffer[:NUM_SENSORS + 1]
            else:
                del buffer[0]

import threading
thread = threading.Thread(target=read_serial_data, daemon=True)
thread.start()

fig, ax = plt.subplots(figsize=(12, 7))
x_data = np.arange(WINDOW_SIZE)
lines = [ax.plot(x_data, data_array[i], lw=1.5)[0] for i in range(NUM_SENSORS)]

# Set Y axis to show full raw range
ax.set_ylim(0, 200)
ax.set_xlim(0, WINDOW_SIZE - 1)
ax.set_title("RAW Capacitive Sensor Values — No Processing")
ax.set_xlabel("Samples")
ax.set_ylabel("Raw Value (0-255)")
ax.grid(True, linestyle='--', alpha=0.4)

def update(frame):
    if is_receiving:
        for i, line in enumerate(lines):
            line.set_ydata(data_array[i])
    return lines

ani = animation.FuncAnimation(
    fig, update, interval=20, blit=False, cache_frame_data=False
)

plt.tight_layout()
plt.show()