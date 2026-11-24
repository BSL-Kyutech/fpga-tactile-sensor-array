#!/usr/bin/env bash
# Start / stop the tactile sensor viewers on Linux (counterpart of viz.cmd on Windows).
#   viz.sh help
# The viewer runs in the background; its output goes to ~/.cache/tactile-viz/<target>.log
set -u

TOOLS="$(cd "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")" && pwd)"
VIS="$(dirname "$TOOLS")"
REPO="$(dirname "$VIS")"
LOGDIR="${XDG_CACHE_HOME:-$HOME/.cache}/tactile-viz"
PATTERN='Visualizer/(icepizeroo|hand_heatmap|hand_calibrate|hand_gain_calibrate)\.py|tools/channel_check\.py'

if [ -n "${VIZ_PYTHON:-}" ]; then PY="$VIZ_PYTHON"
elif [ -x "$VIS/.venv/bin/python" ]; then PY="$VIS/.venv/bin/python"
else PY=python3; fi

script_for() {
    case "$1" in
        graph)   echo "Visualizer/icepizeroo.py" ;;
        hand)    echo "Visualizer/hand_heatmap.py" ;;
        raw|handraw) echo "Visualizer/hand_heatmap.py --raw" ;;
        nocal)   echo "Visualizer/hand_heatmap.py --nocal" ;;
        zero)    echo "Visualizer/hand_heatmap.py --zero" ;;
        calib)   echo "Visualizer/hand_calibrate.py" ;;
        gain)    echo "Visualizer/hand_gain_calibrate.py" ;;
        check)   echo "Visualizer/tools/channel_check.py" ;;
        *) return 1 ;;
    esac
}

running() { pgrep -f -a -- "$PATTERN" | grep -v -- "pgrep" ; }

do_status() {
    if running >/dev/null; then echo "RUNNING:"; running; else echo "STOPPED"; fi
    if ! running >/dev/null; then "$PY" "$TOOLS/probe.py" 2>&1 | tail -1; fi
}

do_stop() {
    local pids
    pids=$(pgrep -f -- "$PATTERN" || true)
    [ -z "$pids" ] && { echo "nothing running"; return 0; }
    kill $pids && echo "stopped pid $pids"
    for _ in 1 2 3 4 5 6 7 8 9 10; do pgrep -f -- "$PATTERN" >/dev/null || return 0; sleep 0.3; done
    kill -9 $(pgrep -f -- "$PATTERN") 2>/dev/null; return 0
}

do_start() {
    local target="$1" script
    script=$(script_for "$target") || { echo "unknown target: $target (see: viz help)"; return 1; }
    if running >/dev/null; then echo "already running:"; running; return 1; fi
    if [ -z "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]; then echo "NG: no display (DISPLAY / WAYLAND_DISPLAY not set)"; return 1; fi
    "$PY" "$TOOLS/probe.py" || { echo "probe failed - not starting (see: viz help)"; return 1; }
    sleep 0.3
    mkdir -p "$LOGDIR"
    cd "$REPO" || return 1
    # shellcheck disable=SC2086
    nohup "$PY" $script > "$LOGDIR/$target.log" 2>&1 &
    local pid=$!
    sleep 3
    if kill -0 "$pid" 2>/dev/null; then echo "OK: $target started (pid $pid, log $LOGDIR/$target.log)"
    else echo "NG: $target exited - last lines of $LOGDIR/$target.log:"; tail -15 "$LOGDIR/$target.log"; return 1; fi
}

usage() {
    cat <<'TXT'
viz - start/stop the tactile sensor viewers (Icepi Zero, port is found automatically)

  viz graph          line graph of all 24 channels (Visualizer/icepizeroo.py)
  viz hand           hand heatmap, force-scale gains + zero calibration applied
  viz raw            hand heatmap without force-scale gains (zero calibration kept)
  viz nocal          hand heatmap without any calibration (no gains, no zero)
  viz zero           hand heatmap + zero calibration at start (hands off 4 s)
  viz calib          re-measure which channel each electrode is (touch each one)
  viz gain           re-measure force-scale gains (press each electrode with the same force)
  viz check          step through S0..S23 one channel at a time
  viz stop           close the running viewer
  viz restart hand   restart (graph / hand / raw / nocal / zero / calib / gain / check)
  viz status         show what is running and whether packets arrive
  viz help           this help

Only one viewer can use the serial port at a time.  Keep hands off for ~1 s after start.
Heatmap keys: r or REC = recording (~/Videos/hand_heatmap), z or ZERO = zero calibration,
              b = re-baseline, g = gains, +/- = colour max, [ / ] or slider = low-pass filter,
              a = divide by electrode area, l = labels
Env: VIZ_PYTHON (python to use), VIZ_PORT (force a port, e.g. /dev/ttyUSB0)
Logs: ~/.cache/tactile-viz/<target>.log
TXT
}

cmd="${1:-status}"
case "$cmd" in
    help|-h|--help) usage ;;
    status)  do_status ;;
    stop)    do_stop ;;
    restart) do_stop; sleep 1; do_start "${2:-hand}" ;;
    start)   do_start "${2:-hand}" ;;
    *)       do_start "$cmd" ;;
esac
