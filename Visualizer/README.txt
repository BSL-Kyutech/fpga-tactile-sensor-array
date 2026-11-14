##Requirements


pip install matplotlib 

pip install pyserial


##Hand heatmap (hand_heatmap.py)

python Visualizer/hand_heatmap.py

Shows the 20 hand taxels as colours on the hand outline (same serial format,
port auto-detection and baseline as icepizeroo.py; keep hands off at start).
Keys: b = re-baseline, + / - = colour scale, l = toggle channel labels.

hand_layout.json holds the taxel shapes and the taxel -> channel (S0..S23) mapping.
The mapping is PROVISIONAL (not yet checked against the hardware): edit "channel"
for each taxel. Channels not on the hand are listed in the status box.

To regenerate hand_layout.json from the hand DXF (layer 0 = outline,
FOOTPRINT = taxel shapes; F2+F3 and F0+F14 are one taxel each):

pip install ezdxf
python Visualizer/tools/extract_hand_layout.py hand_outer_shape_closed_footprint_v3.dxf
