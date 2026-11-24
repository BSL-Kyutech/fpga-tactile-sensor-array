#!/usr/bin/env bash
# One-time setup on a Linux desktop (Ubuntu/Debian tested):
#   bash Visualizer/tools/setup_linux.sh
# - installs python3-venv and python3-tk (matplotlib window) with apt (asks for sudo)
# - creates Visualizer/.venv and installs Visualizer/requirements.txt
# - adds you to the "dialout" group so you can open /dev/ttyUSB* (log out and in once)
# - links ~/.local/bin/viz -> Visualizer/tools/viz.sh
set -eu

TOOLS="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
VIS="$(dirname "$TOOLS")"

if command -v apt-get >/dev/null; then
    echo "== apt: python3-venv python3-tk"
    sudo apt-get update -qq
    sudo apt-get install -y python3-venv python3-tk
else
    echo "!! apt-get not found: install python3 venv + tkinter with your package manager"
fi

echo "== venv: $VIS/.venv"
python3 -m venv "$VIS/.venv"
"$VIS/.venv/bin/pip" install -q --upgrade pip
"$VIS/.venv/bin/pip" install -q -r "$VIS/requirements.txt"
"$VIS/.venv/bin/python" -c "import matplotlib, serial, numpy, imageio_ffmpeg, tkinter; print('python packages OK, matplotlib', matplotlib.__version__)"

if id -nG "$USER" | grep -qw dialout; then
    echo "== $USER is already in dialout"
else
    echo "== adding $USER to dialout (serial port access) - log out and in again afterwards"
    sudo usermod -aG dialout "$USER"
fi

chmod +x "$TOOLS/viz.sh"
mkdir -p "$HOME/.local/bin"
ln -sf "$TOOLS/viz.sh" "$HOME/.local/bin/viz"
echo "== linked ~/.local/bin/viz"
case ":$PATH:" in *":$HOME/.local/bin:"*) ;; *) echo "!! add ~/.local/bin to PATH (new terminal usually does it)";; esac

echo
echo "Done. Plug in the Icepi Zero, then:  viz status   /   viz hand   /   viz help"
