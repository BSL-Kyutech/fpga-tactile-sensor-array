#!/usr/bin/env python3
"""
Trace the copper of the Icepi Zero shield PCB (EAGLE gerbers in
icepizero_PCB_Files/Order_ready_PCB_filess.zip) and print which 40-pin header pin
(and Raspberry-Pi-style GPIO number of the Icepi Zero) each JST connector pad and each
10 MΩ sense resistor is connected to.

  pip install shapely
  python Visualizer/tools/shield_wiring.py [path/to/Order_ready_PCB_filess.zip]

JST pads are numbered 1..20 along the board (x ascending); which end is the connector's
pin 1 is not checked here.  The firmware's channel order (S0..S23) is set by its .lpf,
which this does not know.
"""

import os
import re
import sys
import tempfile
import zipfile

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
DEFAULT_ZIP = os.path.join(REPO, "icepizero_PCB_Files", "Order_ready_PCB_filess.zip")

# Icepi Zero v1.4 header pin -> gpio[n] (cheyao/icepi-zero gateware/v1.4/icepi-zero-v1_4.lpf)
HEADER_GPIO = {27: 0, 28: 1, 3: 2, 5: 3, 7: 4, 29: 5, 31: 6, 26: 7, 24: 8, 21: 9, 19: 10, 23: 11,
               32: 12, 33: 13, 8: 14, 10: 15, 36: 16, 11: 17, 12: 18, 35: 19, 38: 20, 40: 21,
               15: 22, 16: 23, 18: 24, 22: 25, 37: 26, 13: 27}

# board-specific: header JP1 origin and the apertures used for JST pads / 0402 resistor pads
JP1_X, JP1_ROW_Y = 32.50 - 24.13, (73.07, 75.61)
APERTURE_JST, APERTURE_RES = 10, 13


def parse_gerber(path):
    txt = open(path).read()
    ap, cur, x, y, pol = {}, None, 0.0, 0.0, "D"
    shapes, clear, region, in_region = [], [], [], False
    for m in re.finditer(r"%ADD(\d+)([A-Z0-9]+),([^*]*)\*%", txt):
        ap[int(m.group(1))] = (m.group(2), [float(v) for v in m.group(3).split("X") if v])
    body = re.sub(r"%[^%]*%", lambda m: "\n" + m.group(0) + "\n", txt)
    for tok in re.split(r"[*\n]", body):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith("%LP"):
            pol = tok[3]
            continue
        if tok.startswith("%"):
            continue
        if tok == "G36":
            in_region, region = True, []
            continue
        if tok == "G37":
            if len(region) > 2:
                (shapes if pol == "D" else clear).append(Polygon(region).buffer(0))
            in_region = False
            continue
        md = re.match(r"^(?:G54)?D(\d{2,})$", tok)
        if md:
            cur = int(md.group(1))
            continue
        m = re.match(r"^(?:G0?1)?(?:X(-?\d+))?(?:Y(-?\d+))?D0?([123])$", tok)
        if not m:
            continue
        nx = int(m.group(1)) / 1e4 if m.group(1) else x
        ny = int(m.group(2)) / 1e4 if m.group(2) else y
        op = m.group(3)
        if in_region:
            if op == "2":
                if len(region) > 2:
                    (shapes if pol == "D" else clear).append(Polygon(region).buffer(0))
                region = [(nx, ny)]
            else:
                region.append((nx, ny))
        elif op == "1":
            t, p = ap[cur]
            w = min(p[:2]) if t == "R" else p[0]
            g = (LineString([(x, y), (nx, ny)]) if (x, y) != (nx, ny) else Point(nx, ny)).buffer(w / 2)
            (shapes if pol == "D" else clear).append(g)
        elif op == "3":
            t, p = ap[cur]
            g = box(nx - p[0] / 2, ny - p[1] / 2, nx + p[0] / 2, ny + p[1] / 2) if t == "R" \
                else Point(nx, ny).buffer(p[0] / 2)
            (shapes if pol == "D" else clear).append(g)
        x, y = nx, ny
    geo = unary_union(shapes)
    if clear:
        geo = geo.difference(unary_union(clear))
    return list(getattr(geo, "geoms", [geo])), txt


def flashes(txt, aperture):
    pts, cur, x, y = [], None, 0.0, 0.0
    for tok in re.split(r"[*\n]", re.sub(r"%[^%]*%", "", txt)):
        tok = tok.strip()
        md = re.match(r"^(?:G54)?D(\d{2,})$", tok)
        if md:
            cur = int(md.group(1))
            continue
        m = re.match(r"^(?:X(-?\d+))?(?:Y(-?\d+))?D03$", tok)
        if m:
            x = int(m.group(1)) / 1e4 if m.group(1) else x
            y = int(m.group(2)) / 1e4 if m.group(2) else y
            if cur == aperture:
                pts.append((x, y))
    return sorted(pts)


def main():
    zip_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ZIP
    with tempfile.TemporaryDirectory() as tmp:
        zipfile.ZipFile(zip_path).extractall(tmp)
        files = {f: os.path.join(r, f) for r, _, fs in os.walk(tmp) for f in fs}
        top, top_txt = parse_gerber(files["copper_top.gbr"])
        bot, _ = parse_gerber(files["copper_bottom.gbr"])
        holes = []
        for line in open(files["drill_1_64.xln"]):
            m = re.match(r"X(\d+)Y(\d+)", line)
            if m:
                holes.append((int(m.group(1)) / 1000, int(m.group(2)) / 1000))

    layers = {"T": top, "B": bot}
    parent = {(l, i): (l, i) for l in layers for i in range(len(layers[l]))}

    def root(n):
        while parent[n] != n:
            parent[n] = parent[parent[n]]
            n = parent[n]
        return n

    def island(layer, pt):
        for i, g in enumerate(layers[layer]):
            if g.buffer(0.01).contains(Point(pt)):
                return (layer, i)
        return None

    for h in holes:                       # plated holes join top and bottom copper
        a, b = island("T", h), island("B", h)
        if a and b:
            parent[root(a)] = root(b)

    def net(pt):
        i = island("T", pt) or island("B", pt)
        return root(i) if i else None

    header = {}
    for k in range(20):
        hx = JP1_X + 2.54 * k
        header[net((hx, JP1_ROW_Y[0]))] = header.get(net((hx, JP1_ROW_Y[0])), []) + [2 * k + 1]
        header[net((hx, JP1_ROW_Y[1]))] = header.get(net((hx, JP1_ROW_Y[1])), []) + [2 * k + 2]

    def describe(n):
        pins = sorted(header.get(n, []))
        gp = [f"GPIO{HEADER_GPIO[p]}" for p in pins if p in HEADER_GPIO]
        return f"header {pins} {' '.join(gp)}"

    jst = flashes(top_txt, APERTURE_JST)
    jst_net = {}
    print("JST pad -> header pin (GPIO)")
    for i, c in enumerate(jst, 1):
        n = net(c)
        jst_net[n] = i
        print(f"  JST {i:2d}: {describe(n)}")

    res_nets = {}
    for c in flashes(top_txt, APERTURE_RES):
        res_nets.setdefault(net(c), []).append(c)
    print("\nsense resistor nets (1 resistor pad each) not going to the JST:")
    for n, cs in res_nets.items():
        if len(cs) == 1 and n not in jst_net:
            print(f"  {describe(n)}")
    print("\ncommon resistor nets:")
    for n, cs in res_nets.items():
        if len(cs) > 1:
            print(f"  {len(cs)} resistor pads -> {describe(n)}")


if __name__ == "__main__":
    main()
