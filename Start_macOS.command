#!/bin/bash
# StellavitaLogsreader - Start unter macOS / Linux (richtet beim ersten Mal alles selbst ein)
# Doppelklick im Finder, oder im Terminal:  bash Start_macOS.command
cd "$(dirname "$0")" || exit 1

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 fehlt / Python 3 is missing."
  echo "Bitte installieren / please install: https://www.python.org/downloads/macos/"
  read -r -p "Enter zum Beenden / press Enter to quit" _; exit 1
fi

if ! python3 -c "import tkinter" >/dev/null 2>&1; then
  echo "Tkinter fehlt / Tkinter is missing."
  echo "Empfohlen / recommended: Python von python.org installieren (enthaelt Tk) -> https://www.python.org/downloads/macos/"
  echo "Mit Homebrew:  brew install python-tk"
  read -r -p "Enter zum Beenden / press Enter to quit" _; exit 1
fi

if [ ! -x ".venv/bin/python" ]; then
  echo "Erste Einrichtung (einmalig) / first-time setup ..."
  python3 -m venv .venv || { echo "venv fehlgeschlagen / failed"; read -r -p "Enter" _; exit 1; }
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt || { echo "Installation fehlgeschlagen / failed"; read -r -p "Enter" _; exit 1; }
fi

exec .venv/bin/python stellavita_logsreader.py "$@"
