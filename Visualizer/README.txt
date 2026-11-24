##Requirements


pip install matplotlib 

pip install pyserial


##Hand heatmap (hand_heatmap.py)

python Visualizer/hand_heatmap.py            (gains + zero calibration applied)
python Visualizer/hand_heatmap.py --raw      (no force-scale gains, zero calibration kept)
python Visualizer/hand_heatmap.py --nocal    (no calibration at all)
python Visualizer/hand_heatmap.py --zero     (run the zero calibration right after start)
python Visualizer/hand_heatmap.py --vmax 200 --smooth 0.7 --outdir DIR

Shows the 20 hand taxels as colours on the hand outline (same serial format,
port auto-detection and baseline as icepizeroo.py; keep hands off at start).
Keys: r = start/stop recording, z = zero calibration, g = gains on/off,
a = divide by taxel area, + / - = colour scale (default 0-100), [ / ] = low-pass filter,
b = re-baseline, l = toggle channel labels.  Buttons: REC, ZERO; slider: low-pass α.

Zero calibration (ZERO / z, hands off 3 s): stores a per-channel noise floor in
hand_layout.json ("noise_floor") that is subtracted, so the untouched hand shows 0.
Needed e.g. with the conductive silicone cover, which makes large pads noisier.

Low-pass filter: packets of one frame (~30 ms) are averaged, then an exponential moving
average with weight α per frame (α = 1: no extra smoothing).  The status box shows α and
the resulting time constant.

Recording (REC / r): writes to ~/Videos/hand_heatmap (or --outdir)
  hand_YYYYMMDD_HHMMSS.mp4         the window at a constant 30 fps (= wall-clock time)
  hand_YYYYMMDD_HHMMSS_sensor.csv  every packet: unix time, raw S0..S23
  hand_YYYYMMDD_HHMMSS.json        exact start/stop time (ms), frames, baseline
Frame k of the video shows the screen at start_unix + k/30 s, for syncing with a camera.
Needs: pip install imageio-ffmpeg (bundles ffmpeg).

hand_layout.json holds the taxel shapes, the taxel -> channel (S0..S23) mapping and
the per-taxel gains.  The 24 values in a packet include 4 channels that are not wired
to the hand (S2, S16, S19, S21 on the current board); they are listed in the status box.

The mapping was measured by touch and is TEMPORARY: it should be replaced by the
mapping derived from the pin constraints (.lpf) of the firmware actually flashed
(icepizero_code/icepi-zero.lpf in this repo is empty).  ring_tip = S9 is inferred;
S9 reads a constant 1200 and does not respond.

##Calibration tools

python Visualizer/hand_calibrate.py
  Touch the highlighted taxel; the channel that responds most is assigned.
  Click a taxel to choose it, Skip / Back / Save buttons.  Writes "channel" in hand_layout.json.

python Visualizer/hand_gain_calibrate.py
  Press every taxel with the same force (2-3 times each).  "Save gains" writes
  gain = median of all channels / median press value of the channel to hand_layout.json,
  so equal force shows as an equal value.  Presses are logged in gain_events.json.

##Regenerating hand_layout.json from the hand DXF

(layer 0 = outline, FOOTPRINT = taxel shapes; F2+F3 and F0+F14 are one taxel each)

pip install ezdxf
python Visualizer/tools/extract_hand_layout.py hand_outer_shape_closed_footprint_v3.dxf

This resets "channel" to a placeholder order and drops the gains.

##Launcher and diagnostic tools (Visualizer/tools, Windows)

viz.cmd / vizctl.ps1   start a viewer in its own cmd window after checking that packets arrive.
                       Add Visualizer\tools to PATH (user environment variable), then in a NEW terminal:
                       viz graph | viz hand | viz raw | viz calib | viz gain | viz check | viz stop | viz status
                       (viz.cmd runs vizctl.ps1 with -ExecutionPolicy Bypass, so no policy change is needed.
                        Python: VIZ_PYTHON env var, else per-user Python 3.13, else "python".)
probe.py               find the board (FTDI 0403:6015) and count packets for 1.5 s, no plot.
channel_check.py       step through S0..S23 one at a time while touching the hand.
watch_channels.py      log which channels move while touching (finds dead / stuck / shorted channels).
sim_heatmap.py         render hand_heatmap.py to a PNG with fake data (no board needed).
shield_wiring.py       trace the shield PCB gerbers: JST pad -> header pin -> GPIO (needs shapely).

##Hardware notes (Icepi Zero shield + hand sensor, found 2026-11-13..16)

- Shield wiring (from icepizero_PCB_Files gerbers, shield_wiring.py):
    JST  1..10 -> header 3, 5, 7, 11, 12, 13, 15, 16, 18, 22  = GPIO 2, 3, 4, 17, 18, 27, 22, 23, 24, 25
    JST 11..20 -> header 26, 27, 28, 29, 31, 32, 33, 35, 36, 37 = GPIO 7, 0, 1, 5, 6, 12, 13, 19, 16, 26
  24 x 10 MΩ sense resistors pull up to 5V (header 2/4); 4 of them (header 8, 10, 38, 40 =
  GPIO 14, 15, 20, 21) have no JST pin.  The firmware sends all 24 (GPIO 0-27 minus SPI 8-11).
- Channels not wired to the hand: S2, S16, S19, S21 (constant 1-6 counts).
- S9 reads a constant 1200 and never responds (hand map: ring_tip, inferred).
- 2026-11-16: S13 (index_tip) and S18 (index_mid) always respond together with the same value
  and their idle counts dropped from ~70 to ~25 -> probably shorted to each other; check the flex
  on the index finger and the JST connector.
- The channel order S0..S23 is set by the flashed firmware's .lpf, which is not in this repo
  (icepizero_code/icepi-zero.lpf and Makefile are empty; top.sv here is a 20-ch SPI version).
