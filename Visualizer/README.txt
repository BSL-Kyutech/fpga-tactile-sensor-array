##Requirements


pip install matplotlib 

pip install pyserial


##Hand heatmap (hand_heatmap.py)

python Visualizer/hand_heatmap.py          (force-scale gains applied)
python Visualizer/hand_heatmap.py --raw    (sensor values as they are)
python Visualizer/hand_heatmap.py --vmax 200

Shows the 20 hand taxels as colours on the hand outline (same serial format,
port auto-detection and baseline as icepizeroo.py; keep hands off at start).
Keys: g = gains on/off, a = divide by taxel area, + / - = colour scale (default 0-100),
b = re-baseline, l = toggle channel labels.

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
