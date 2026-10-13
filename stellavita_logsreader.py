#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# StellavitaLogsreader - Copyright (C) 2026 marzibasti-droid
# https://github.com/marzibasti-droid/StellavitaLogsreader
#
# This program is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details: <https://www.gnu.org/licenses/>.
"""
StellavitaLogsreader - Viewer fuer StellaVita-Guiding-Logs
=================================================

Liest die (verschleierten) Logdateien der StellaVita-Box und der App:

  * GuideLog_*.txt   Box-Log im PHD2-Stil (jeder Guiding-Frame, Drops, Dither, ...)
  * Logs_App_*.txt   App-Log (Guiding-Ereignisse, Leitstern-HFD, Autofokus-Kurven)

und zeigt einen Guide-Graph mit Zoom/Pan, Statistik und HFD/HFR-Auswertung.

Start:        python stellavita_logsreader.py [Dateien ...]
Nur Tabelle:  python stellavita_logsreader.py --summary Datei1 Datei2 ...
Entschluesseln: python stellavita_logsreader.py --decode Datei [Ausgabe]

Benoetigt: Python 3.9+, numpy, matplotlib (Tkinter ist bei Python fuer Windows dabei).
"""
from __future__ import annotations

import argparse
import calendar
import csv
import json
import math
import os
import queue
import re
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone

def _ensure_deps():
    """Fehlende Pakete (numpy, matplotlib) auf Nachfrage per pip installieren. / Offer to pip-install missing packages."""
    import importlib.util
    import subprocess
    if getattr(sys, "frozen", False):          # EXE: alles bereits enthalten
        return
    need = [p for p in ("numpy", "matplotlib") if importlib.util.find_spec(p) is None]
    if not need:
        return
    msg = ("Folgende Pakete fehlen: %s\nJetzt automatisch installieren (pip)?\n\n"
           "Missing packages: %s\nInstall now (pip)?" % (", ".join(need), ", ".join(need)))
    ok = None
    try:
        import tkinter as tk
        from tkinter import messagebox
        r = tk.Tk()
        r.withdraw()
        ok = messagebox.askyesno("StellavitaLogsreader", msg)
        r.destroy()
    except Exception:  # noqa: BLE001  (kein Tkinter -> Konsole)
        try:
            ok = input(msg.replace("\n\n", "\n") + " [j/y/n] ").strip().lower() in ("j", "y", "ja", "yes")
        except EOFError:
            ok = False
    if not ok:
        sys.exit("Bitte installieren / please install:  python -m pip install " + " ".join(need))
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade"] + need
    if subprocess.call(cmd) != 0:
        cmd.insert(5, "--user")
        if subprocess.call(cmd) != 0:
            sys.exit("Installation fehlgeschlagen / failed:  python -m pip install " + " ".join(need))
    importlib.invalidate_caches()


_ensure_deps()
import numpy as np  # noqa: E402

__version__ = "1.0.0"
APP_NAME = "StellavitaLogsreader"
DEFAULT_SCALE = 1.68          # Bogensekunden pro Pixel, falls im Log nichts steht
DEFAULT_BOX_OFFSET_H = -1.0   # Box-Zeitstempel laufen 1 h vor der Ortszeit
PULSE_LIMIT_MS = 2400         # ab hier gilt ein Puls als "am Limit" (max. 2500 ms)

# --------------------------------------------------------------------------- i18n
_TR = {
    "title": ("StellavitaLogsreader – StellaVita Guiding-Logs", "StellavitaLogsreader – StellaVita guiding logs"),
    "open_files": ("Dateien öffnen…", "Open files…"),
    "open_folder": ("Ordner öffnen…", "Open folder…"),
    "offset": ("Box-Zeit → Ortszeit (h):", "Box time → local (h):"),
    "auto": ("Auto", "Auto"),
    "unit": ("Einheit:", "Unit:"),
    "arcsec": ("Bogensek. (″)", "Arcsec (″)"),
    "px": ("Pixel", "Pixels"),
    "starmode": ("Stern:", "Star:"),
    "show": ("Anzeige:", "Show:"),
    "ra": ("RA", "RA"),
    "dec": ("Dec", "Dec"),
    "drops": ("Verworfene", "Dropped"),
    "dither": ("Dither", "Dither"),
    "events": ("Ereignisse", "Events"),
    "pulses": ("Pulse", "Pulses"),
    "starpanel": ("Leitstern", "Guide star"),
    "yauto": ("Y-Auto", "Y auto"),
    "excl": ("Einschwingen ausschließen", "Exclude settling"),
    "sessions": ("Guiding-Sitzungen", "Guiding sessions"),
    "afruns": ("Autofokus-Läufe", "Autofocus runs"),
    "stats": ("Statistik (sichtbarer Bereich)", "Statistics (visible range)"),
    "col_nr": ("Nr", "No"),
    "col_start": ("Start", "Start"),
    "col_end": ("Ende", "End"),
    "col_dur": ("Dauer", "Dur."),
    "col_side": ("Seite", "Side"),
    "col_frames": ("Frames", "Frames"),
    "col_drop": ("Drop %", "Drop %"),
    "col_rms": ("RMS ″", "RMS ″"),
    "col_dith": ("Dither", "Dith."),
    "col_fail": ("Fehl.", "Fail"),
    "col_res": ("Ergebnis", "Result"),
    "col_pos": ("Bestpos.", "Best pos."),
    "col_pts": ("Punkte", "Pts"),
    "af_ok": ("OK", "OK"),
    "af_err": ("Fehler {}", "Error {}"),
    "af_open": ("läuft/offen", "open"),
    "reset": ("Gesamt", "Fit all"),
    "zoom_in": ("+", "+"),
    "zoom_out": ("–", "–"),
    "png": ("PNG…", "PNG…"),
    "hint": ("Mausrad: Zoom · Ziehen: verschieben · Rechtsklick-Ziehen: Bereich markieren (mehrere möglich, Rechtsklick auf Bereich entfernt ihn) · Esc: Auswahl löschen · Doppelklick: alles",
             "Wheel: zoom · drag: pan · right-drag: mark range (several possible, right-click on a range removes it) · Esc: clear selection · double-click: fit"),
    "menu_file": ("Datei", "File"),
    "menu_lang": ("Sprache", "Language"),
    "menu_help": ("Hilfe", "Help"),
    "save_decoded": ("Entschlüsselte Dateien speichern…", "Save decoded files…"),
    "export_csv": ("Auswahl/sichtbaren Bereich als CSV…", "Export selection/visible range as CSV…"),
    "quit": ("Beenden", "Quit"),
    "about": ("Über", "About"),
    "about_text": (
        "StellavitaLogsreader {}\nViewer für StellaVita-Guiding-Logs.\n\n"
        "Markenrechtlicher Hinweis:\nUnabhängiges Open-Source-Werkzeug der Community für die Community. "
        "Keine geschäftliche, rechtliche oder organisatorische Verbindung zu ToupTek Astro oder deren Partnern. "
        "„ToupTek“ und „StellaVita“ sind Marken der jeweiligen Eigentümer; die Namen dienen nur der "
        "Beschreibung der Kompatibilität.\n\n"
        "Haftungsausschluss:\nDie Software wird „wie besehen“ (as is) ohne ausdrückliche oder "
        "stillschweigende Garantie bereitgestellt. Keine Haftung für Hardwareschäden, Datenverlust oder "
        "entgangene Aufnahmesessions. Nutzung auf eigene Gefahr.\n\n"
        "Quelle / Lizenz: GPL-3.0 – https://github.com/marzibasti-droid/StellavitaLogsreader\n\nDatenschutz:\nLogdateien werden ausschließlich lokal auf Ihrem Rechner verarbeitet. Es werden keine "
        "Daten (z. B. Standort/GPS) an Server übertragen oder dort gespeichert.",
        "StellavitaLogsreader {}\nViewer for StellaVita guiding logs.\n\n"
        "Trademark notice:\nIndependent open-source tool by the community, for the community. "
        "Not affiliated with, endorsed by or connected to ToupTek Astro or its partners. "
        "\"ToupTek\" and \"StellaVita\" are trademarks of their respective owners; the names are used only "
        "to describe compatibility.\n\n"
        "Disclaimer:\nThe software is provided \"as is\", without warranty of any kind, express or implied. "
        "No liability for hardware damage, data loss or lost imaging sessions. Use at your own risk.\n\n"
        "Source / license: GPL-3.0 – https://github.com/marzibasti-droid/StellavitaLogsreader\n\nPrivacy:\nLog files are processed locally on your computer only. No data (e.g. location/GPS) is "
        "transmitted to or stored on any server."),
    "loading": ("Lade {} …", "Loading {} …"),
    "loaded": ("{} Datei(en) geladen · {} Frames · {} Drops · {} Sitzungen",
               "{} file(s) loaded · {} frames · {} drops · {} sessions"),
    "offset_auto": ("Zeitversatz automatisch erkannt: {} h", "Time offset detected automatically: {} h"),
    "offset_none": ("Kein Zeitversatz erkennbar (App- und Box-Log nötig).",
                    "Could not detect offset (needs app and box log)."),
    "unknown_file": ("Unbekanntes Format: {}", "Unknown format: {}"),
    "nodata": ("Keine Guiding-Daten in den geladenen Dateien.", "No guiding data in the loaded files."),
    "no_view": ("Erst Dateien öffnen.", "Open files first."),
    "saved": ("Gespeichert: {}", "Saved: {}"),
    "err": ("Fehler", "Error"),
    "range": ("Zeitraum", "Range"),
    "sel_title": ("AUSWAHL", "SELECTION"),
    "sel_keep_info": ("{} Bereich(e), zusammen {}", "{} range(s), total {}"),
    "sel_drop_info": ("sichtbarer Bereich ohne {} markierte(n) Bereich(e) ({})",
                      "visible range without {} marked range(s) ({})"),
    "mode_keep": ("Nur Auswahl", "Selection only"),
    "mode_drop": ("Auswahl ausschließen", "Exclude selection"),
    "clear_sel": ("Auswahl löschen", "Clear selection"),
    "show_data": ("Daten…", "Data…"),
    "data_title": ("Daten der Auswahl", "Selection data"),
    "data_cols": ("Zeit,RA ″,Dec ″,RA px,Dec px,RA ms,Dec ms,SNR", "Time,RA ″,Dec ″,RA px,Dec px,RA ms,Dec ms,SNR"),
    "data_more": ("(nur die ersten {} von {} Zeilen – Export enthält alle)", "(first {} of {} rows only – export has all)"),
    "frames_line": ("Frames", "Frames"),
    "dropped": ("verworfen", "dropped"),
    "longest": ("längste Serie", "longest run"),
    "rms_line": ("RMS RA / Dec / ges.", "RMS RA / Dec / total"),
    "peak_line": ("Max. Fehler", "Peak error"),
    "snr_line": ("SNR min / Median", "SNR min / median"),
    "pulse_line": ("Frames mit Puls", "Frames with pulse"),
    "limit_line": ("Pulse am Limit", "Pulses at limit"),
    "dither_line": ("Dither", "Dithers"),
    "settle_line": ("Settle ok / fehlgeschl.", "Settle ok / failed"),
    "lost_line": ("Stern verloren (App)", "Star lost (app)"),
    "hfd_title": ("Leitstern HFD / HFR (px)", "Guide star HFD / HFR (px)"),
    "hfd_n": ("Messwerte", "Samples"),
    "hfd_minmax": ("HFD min / max", "HFD min / max"),
    "hfd_med": ("HFD Median / Mittel", "HFD median / mean"),
    "hfd_std": ("HFD Std.abw.", "HFD std dev"),
    "hfr_med": ("HFR Median", "HFR median"),
    "hfd_none": ("(HFD braucht App-Logs)", "(HFD needs app logs)"),
    "af_title": ("Autofokus im Bereich", "Autofocus in range"),
    "pxscale": ("Pixelmaßstab", "Pixel scale"),
    "device": ("Gerät", "Device"),
    "err_ylabel_as": ("Fehler (″)", "Error (″)"),
    "err_ylabel_px": ("Fehler (px)", "Error (px)"),
    "pulse_ylabel": ("Puls (ms)", "Pulse (ms)"),
    "no_pulse": ("keine Pulsdaten (Box-Log laden)", "no pulse data (load box log)"),
    "snr": ("SNR", "SNR"),
    "hfd_ylabel": ("HFD (px)", "HFD (px)"),
    "hfr_ylabel": ("HFR (px)", "HFR (px)"),
    "hfd_note": ("HFD braucht App-Logs – hier SNR", "HFD needs app logs – showing SNR"),
    "calib": ("Kalibrierung", "Calibration"),
    "settle_fail": ("Settle fehlgeschlagen", "Settle failed"),
    "star_lost": ("Stern verloren", "Star lost"),
    "autofocus": ("Autofokus", "Autofocus"),
    "csv_cols": ("zeit,frame,ra_px,dec_px,ra_arcsec,dec_arcsec,ra_puls_ms,dec_puls_ms,snr,masse",
                 "time,frame,ra_px,dec_px,ra_arcsec,dec_arcsec,ra_pulse_ms,dec_pulse_ms,snr,mass"),
}
LANG = "de"


def tr(key: str, *args) -> str:
    pair = _TR.get(key)
    s = pair[0 if LANG == "de" else 1] if pair else key
    return s.format(*args) if args else s


# ----------------------------------------------------------------------- decoding
# Die Logs sind mit einem laufenden Zeichenversatz verschleiert:
#   sichtbare ASCII-Zeichen (32..126) zaehlen hoch (n = 0, 1, 2, ...),
#   Schluessel k = 32 + (n mod 95),  Klartext p = 32 + ((c - 32 - k) mod 94).
# Zeilenumbrueche und Nicht-ASCII-Zeichen bleiben unveraendert und zaehlen nicht mit.
def _shift(raw: bytes, n0: int = 0) -> bytes:
    a = np.frombuffer(raw, dtype=np.uint8)
    m = (a >= 32) & (a <= 126)
    out = a.astype(np.int32)
    idx = np.cumsum(m, dtype=np.int64) - 1 + n0
    key = 32 + (idx % 95)
    dec = 32 + ((out - 32 - key) % 94)
    return np.where(m, dec, out).astype(np.uint8).tobytes()


_KEYS = (b"Log begin", b"Platform:", b"Version", b"Guiding", b"logCallback",
         b"Calibration", b"CoreClient", b"Frame Dropped")
_TSB = re.compile(rb"\d{4}-\d\d-\d\d \d\d:\d\d:\d\d")


def _score(b: bytes) -> int:
    return 3 * len(_TSB.findall(b)) + sum(b.count(k) for k in _KEYS)


def decode_log(raw: bytes):
    """-> (text | None, info). Erkennt Klartext und den Startversatz selbst."""
    head = raw[:8000]
    base = _score(head)
    best = max(range(95), key=lambda n: _score(_shift(head, n)))
    bs = _score(_shift(head, best))
    if base >= 3 and base >= bs:
        return raw.decode("utf-8", "replace"), {"plain": True, "n0": None}
    if bs < 3:
        return None, {"plain": False, "n0": None}
    return _shift(raw, best).decode("utf-8", "replace"), {"plain": False, "n0": best}


# ------------------------------------------------------------------------ parsing
def _ts(s: str) -> float:
    return float(calendar.timegm((int(s[0:4]), int(s[5:7]), int(s[8:10]),
                                  int(s[11:13]), int(s[14:16]), int(s[17:19]))))


_T = r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)"
RE_STEP = re.compile(
    "^" + _T + r': Guiding Step-> FrameNum-(\d+), StepTime-([\d.]+), "Mount", '
    r"CamOffsetX-(-?[\d.]+), CamOffsetY-(-?[\d.]+), MountOffsetX-(-?[\d.]+), "
    r"MountOffsetY-(-?[\d.]+), DistRa-(-?[\d.]+), DistDec-(-?[\d.]+), "
    r"DurRa-(\d+) \((\w*)\), DurDec-(\d+) \((\w*)\)\s+StarMass-(\d+), "
    r"StarSNR-([\d.]+), StarErr-(\d+)")
RE_DROP = re.compile("^" + _T + r": Guiding Frame Dropped-> FrameNum-(\d+).*?StarMass-(\d+), "
                     r"StarSNR-([\d.]+), StarErr-(\d+)")
RE_EV = re.compile("^" + _T + r": (Guiding Begins|Guiding Ends|Calibration Begins|"
                   r"Calibration Complete|Guiding Dithered)")
RE_APP = re.compile("^" + _T + r' \| logCallback: \[CoreClient\]\[EVT\] '
                    r'\{"event_type":"(EVT_[A-Z_]+)":(\{.*\})\}\s*$')
_SIGN = {"E": 1.0, "N": 1.0, "W": -1.0, "S": -1.0}


def parse_box(text: str) -> dict:
    frames, drops, events, sessions, head = [], [], [], [], []
    scale = None
    cur = None
    last_t = None
    for line in text.splitlines():
        if not line:
            continue
        if line[:4].isdigit() and line[4:5] == "-" and len(line) > 19:
            t = _ts(line[:19])
            last_t = t
            s = RE_STEP.match(line)
            if s:
                g = s.groups()
                rap = float(g[9]) * _SIGN.get(g[10], 0.0)
                decp = float(g[11]) * _SIGN.get(g[12], 0.0)
                frames.append((t, int(g[1]), float(g[5]), float(g[6]), rap, decp,
                               float(g[14]), float(g[13])))
                continue
            d = RE_DROP.match(line)
            if d:
                drops.append((t, int(d.group(2)), int(d.group(5)),
                              float(d.group(4)), float(d.group(3))))
                continue
            m = RE_EV.match(line)
            if m:
                kind = m.group(2)
                if kind == "Guiding Begins":
                    cur = {"start": t, "end": None, "pier": "", "info": {}}
                    sessions.append(cur)
                    events.append((t, "begin", ""))
                elif kind == "Guiding Ends":
                    if cur is not None and cur["end"] is None:
                        cur["end"] = t
                        cur = None
                    if not events or events[-1][:2] != (t, "end"):
                        events.append((t, "end", ""))
                elif kind == "Calibration Begins":
                    events.append((t, "calib_begin", ""))
                elif kind == "Calibration Complete":
                    events.append((t, "calib_end", ""))
                else:
                    events.append((t, "dither", ""))
            continue
        # Zeilen ohne Zeitstempel: Kopf, Settling, Dither, Sitzungs-Header
        if line.startswith(("Log begin", "Platform:", "Version")):
            if len(head) < 6:
                head.append(line.strip())
        elif line.startswith("INFO:"):
            if last_t is None:
                continue
            if "Settling started" in line:
                events.append((last_t, "settle_start", ""))
            elif "Settling complete" in line:
                events.append((last_t, "settle_ok", ""))
            elif "Settling failed" in line:
                events.append((last_t, "settle_fail", ""))
            elif line.startswith("INFO: DITHER by") and events and events[-1][1] == "dither":
                events[-1] = (events[-1][0], "dither", line[len("INFO: DITHER by"):].split(", new")[0].strip())
        else:
            m = re.search(r"Pixel scale = ([\d.]+) arc-sec/px", line)
            if m and scale is None:
                scale = float(m.group(1))
            if cur is not None and cur["end"] is None:
                m = re.search(r"Pier side = (\w+)", line)
                if m and not cur["pier"]:
                    cur["pier"] = m.group(1)
                m = re.search(r"parity = (\S+)", line)
                if m:
                    cur["info"]["parity"] = m.group(1)
                m = re.search(r"Exposure = ([\d.]+) ms", line)
                if m:
                    cur["info"]["exposure_ms"] = float(m.group(1))
                m = re.search(r"HFD = ([\d.]+) px", line)
                if m:
                    cur["info"]["hfd0"] = float(m.group(1))
    for s in sessions:
        if s["end"] is None:
            s["end"] = frames[-1][0] if frames else (last_t or s["start"])
    return {"frames": frames, "drops": drops, "events": events,
            "sessions": sessions, "head": head, "scale": scale}


def parse_app(text: str) -> dict:
    steps, hfd, lost, events, af = [], [], [], [], []
    scale = None
    cur_af = None
    for line in text.splitlines():
        if "[CoreClient][EVT]" not in line:
            continue
        if "EVT_GUIDE_" not in line and "EVT_AUTOFOCUS_" not in line:
            continue
        if "AUTOFOCUS_UPDATE_STAR" in line or "AUTOFOCUS_CAPTURE" in line:
            continue
        m = RE_APP.match(line)
        if not m:
            continue
        t = _ts(m.group(1))
        name = m.group(2)
        try:
            j = json.loads(m.group(3))
        except ValueError:
            continue
        if name == "EVT_GUIDE_STEP":
            steps.append((t, float(j.get("offset_ra", 0)), float(j.get("offset_dec", 0)),
                          float(j.get("star_snr", 0)), float(j.get("star_mass", 0)),
                          float(j.get("star_hfd", 0)), int(bool(j.get("is_ra_limited"))),
                          int(bool(j.get("is_dec_limited"))),
                          float(j.get("duration_ra", 0)), float(j.get("duration_dec", 0))))
        elif name == "EVT_GUIDE_STAR_PROFILE_UPDATE":
            if j.get("hfd", 0) > 0:
                hfd.append((t, float(j["hfd"])))
        elif name == "EVT_GUIDE_STAR_LOST":
            lost.append((t, float(j.get("snr", 0))))
            events.append((t, "star_lost", ""))
        elif name == "EVT_GUIDE_GRAPH":
            if j.get("pixel_scale", 0) > 0 and scale is None:
                scale = float(j["pixel_scale"])
        elif name == "EVT_GUIDE_START":
            events.append((t, "begin", ""))
        elif name == "EVT_GUIDE_STOP":
            events.append((t, "end", ""))
        elif name == "EVT_GUIDE_CALIBRATION_START":
            events.append((t, "calib_begin", ""))
        elif name == "EVT_GUIDE_CALIBRATION_STOP":
            events.append((t, "calib_end", ""))
        elif name == "EVT_GUIDE_SETTLE_START":
            events.append((t, "settle_start", ""))
        elif name == "EVT_GUIDE_SETTLE_STOP":
            ok = j.get("status_message") == "success"
            events.append((t, "settle_ok" if ok else "settle_fail", ""))
        elif name == "EVT_GUIDE_DITHER_STEP":
            events.append((t, "dither", "%.1f, %.1f" % (j.get("offset_x", 0), j.get("offset_y", 0))))
        elif name == "EVT_AUTOFOCUS_START":
            cur_af = {"start": t, "end": None, "code": None, "best": None, "pts": ()}
            af.append(cur_af)
            events.append((t, "af_start", ""))
        elif name == "EVT_AUTOFOCUS_UPDATE":
            if cur_af is not None and cur_af["end"] is None:
                cur_af["pts"] = tuple((p["position"], p["hfr"]) for p in j.get("point_array", []))
        elif name == "EVT_AUTOFOCUS_STOP":
            if cur_af is None or cur_af["end"] is not None:
                cur_af = {"start": t, "end": None, "code": None, "best": None, "pts": ()}
                af.append(cur_af)
            cur_af["end"] = t
            cur_af["code"] = j.get("error_code")
            p = j.get("point") or {}
            if p:
                cur_af["best"] = (p.get("position"), p.get("hfr"))
            events.append((t, "af_stop", ""))
    return {"steps": steps, "hfd": hfd, "lost": lost, "events": events, "af": af, "scale": scale}


# --------------------------------------------------------------------- data model
@dataclass
class Session:
    nr: int
    start: float
    end: float
    pier: str = ""
    info: dict = field(default_factory=dict)


@dataclass
class AFRun:
    start: float
    end: float
    code: object
    best: object
    pts: tuple


@dataclass
class View:
    """Alles, was Diagramm und Statistik brauchen (Zeiten in Ortszeit, Sekunden)."""
    src: str = ""
    scale: float = DEFAULT_SCALE
    t: np.ndarray = field(default_factory=lambda: np.zeros(0))
    ra: np.ndarray = field(default_factory=lambda: np.zeros(0))      # px
    dec: np.ndarray = field(default_factory=lambda: np.zeros(0))     # px
    rap: np.ndarray = field(default_factory=lambda: np.zeros(0))     # ms, vorzeichenbehaftet
    decp: np.ndarray = field(default_factory=lambda: np.zeros(0))
    snr: np.ndarray = field(default_factory=lambda: np.zeros(0))
    mass: np.ndarray = field(default_factory=lambda: np.zeros(0))
    has_pulse: bool = False
    dt: np.ndarray = field(default_factory=lambda: np.zeros(0))      # verworfene Frames
    hfd_t: np.ndarray = field(default_factory=lambda: np.zeros(0))
    hfd: np.ndarray = field(default_factory=lambda: np.zeros(0))
    lost_t: np.ndarray = field(default_factory=lambda: np.zeros(0))
    events: list = field(default_factory=list)
    sessions: list = field(default_factory=list)
    af: list = field(default_factory=list)
    settle: list = field(default_factory=list)
    head: list = field(default_factory=list)
    t0: float = 0.0
    t1: float = 1.0


class LogData:
    def __init__(self):
        self.files = []     # (name, art, info)
        self.box = {"frames": [], "drops": [], "events": [], "sessions": [], "head": []}
        self.app = {"steps": [], "hfd": [], "lost": [], "events": [], "af": []}
        self.scale = None

    # -- laden ----------------------------------------------------------------
    def add_file(self, name: str, raw: bytes):
        text, info = decode_log(raw)
        if text is None:
            self.files.append((name, "?", info))
            return "?"
        if "logCallback" in text[:200000] or "[CoreClient]" in text[:200000]:
            p = parse_app(text)
            for k in ("steps", "hfd", "lost", "events"):
                self.app[k].extend(p[k])
            self.app["af"].extend(p["af"])
            art = "app"
        else:
            p = parse_box(text)
            for k in ("frames", "drops", "events", "sessions", "head"):
                self.box[k].extend(p[k])
            art = "box"
        if p["scale"] and not self.scale:
            self.scale = p["scale"]
        info["text"] = text
        self.files.append((name, art, info))
        return art

    def decoded_texts(self):
        return [(n, i["text"]) for n, a, i in self.files if a != "?" and "text" in i]

    # -- Zeitversatz zwischen Box- und App-Log --------------------------------
    def suggest_offset(self):
        b = [t for t, k, _ in self.box["events"] if k == "begin"]
        a = [t for t, k, _ in self.app["events"] if k == "begin"]
        if not b or not a:
            return None
        best, best_n = None, 0
        for h in range(-12, 13):
            n = sum(1 for tb in b if any(abs(ta - (tb + h * 3600)) <= 5 for ta in a))
            if n > best_n:
                best, best_n = float(h), n
        return best

    # -- Ansicht erzeugen -----------------------------------------------------
    def build_view(self, offset_h: float = DEFAULT_BOX_OFFSET_H) -> View:
        off = offset_h * 3600.0
        v = View(scale=self.scale or DEFAULT_SCALE)
        sc = v.scale
        bf = sorted(set(self.box["frames"]))
        steps = sorted(set(self.app["steps"]))
        if bf:
            a = np.array(bf, float)
            v.src = "box"
            v.t = a[:, 0] + off
            v.ra, v.dec, v.rap, v.decp = a[:, 2], a[:, 3], a[:, 4], a[:, 5]
            v.snr, v.mass = a[:, 6], a[:, 7]
            v.has_pulse = True
            bd = sorted(set(self.box["drops"]))
            v.dt = np.array([d[0] for d in bd], float) + off if bd else np.zeros(0)
        elif steps:
            a = np.array(steps, float)
            v.src = "app"
            v.t = a[:, 0]
            v.ra, v.dec = a[:, 1] / sc, a[:, 2] / sc
            v.rap = np.full(len(v.t), np.nan)
            v.decp = np.full(len(v.t), np.nan)
            v.snr, v.mass = a[:, 3], a[:, 4]
            lost0 = sorted({t for t, s in self.app["lost"] if s == 0})
            v.dt = np.array(lost0, float)
        # HFD des Leitsterns (nur App-Logs)
        hf = [(s[0], s[5]) for s in steps if s[5] > 0] + [(t, h) for t, h in set(self.app["hfd"])]
        hf = sorted(set(hf))
        if hf:
            h = np.array(hf, float)
            v.hfd_t, v.hfd = h[:, 0], h[:, 1]
        v.lost_t = np.array(sorted({t for t, s in self.app["lost"]}), float)
        # Ereignisse
        ev = []
        if bf or self.box["events"]:
            ev += [(t + off, k, x) for t, k, x in self.box["events"]]
            ev += [e for e in self.app["events"] if e[1] in ("star_lost", "af_start", "af_stop")]
        else:
            ev += list(self.app["events"])
        v.events = sorted(set(ev))
        # Sitzungen
        if self.box["sessions"]:
            ss = sorted(self.box["sessions"], key=lambda s: s["start"])
            v.sessions = [Session(i + 1, s["start"] + off, s["end"] + off, s["pier"], s["info"])
                          for i, s in enumerate(ss)]
        elif len(v.t):
            ends = [t for t, k, _ in v.events if k == "end"]
            start = v.t[0]
            nr = 0
            for i in range(1, len(v.t) + 1):
                brk = i == len(v.t) or (v.t[i] - v.t[i - 1] > 120) or \
                    any(v.t[i - 1] < e <= v.t[i] for e in ends)
                if brk:
                    nr += 1
                    v.sessions.append(Session(nr, start, v.t[i - 1]))
                    if i < len(v.t):
                        start = v.t[i]
        # Autofokus
        v.af = [AFRun(r["start"], r["end"] if r["end"] else r["start"], r["code"], r["best"], r["pts"])
                for r in {r["start"]: r for r in self.app["af"]}.values()]
        v.af.sort(key=lambda r: r.start)
        # Einschwingfenster (Dither/Start -> Settle fertig)
        opn = None
        for t, k, _ in v.events:
            if k == "settle_start":
                opn = t
            elif k in ("settle_ok", "settle_fail") and opn is not None:
                v.settle.append((opn, t))
                opn = None
        v.head = list(dict.fromkeys(self.box["head"]))
        if len(v.t):
            v.t0, v.t1 = float(v.t[0]), float(v.t[-1])
        elif v.events:
            v.t0, v.t1 = v.events[0][0], v.events[-1][0]
        if v.t1 <= v.t0:
            v.t1 = v.t0 + 1
        return v


# --------------------------------------------------------------------- statistics
def _rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else float("nan")


def sel_mask(arr, t0: float, t1: float, sel=None, mode: str = "keep"):
    """Maske fuer Zeiten in [t0,t1]; mit sel (Liste von (a,b)): nur dort ('keep') bzw. ausserhalb ('drop')."""
    arr = np.asarray(arr, float)
    m = (arr >= t0) & (arr <= t1)
    if sel:
        u = np.zeros(len(arr), bool)
        for a, b in sel:
            u |= (arr >= a) & (arr <= b)
        m &= u if mode == "keep" else ~u
    return m


def compute_stats(v: View, t0: float, t1: float, exclude_settle: bool = True, sel=None, mode: str = "keep") -> dict:
    s = {"t0": t0, "t1": t1}
    if sel and mode == "keep":
        s["t0"], s["t1"] = min(a for a, _ in sel), max(b for _, b in sel)
        t0, t1 = s["t0"], s["t1"]
    s["nsel"] = len(sel) if sel else 0
    s["sel_mode"] = mode
    s["sel_dur"] = sum(b - a for a, b in sel) if sel else 0.0
    m = sel_mask(v.t, t0, t1, sel, mode)
    md = sel_mask(v.dt, t0, t1, sel, mode)
    n, nd = int(m.sum()), int(md.sum())
    s["n"], s["ndrop"] = n, nd
    s["drop_pct"] = 100.0 * nd / (n + nd) if n + nd else 0.0
    if nd:
        allt = np.concatenate([v.t[m], v.dt[md]])
        flag = np.concatenate([np.zeros(n), np.ones(nd)])
        fl = flag[np.argsort(allt, kind="stable")]
        d = np.diff(np.concatenate(([0.0], fl, [0.0])))
        st_, en_ = np.where(d == 1)[0], np.where(d == -1)[0]
        s["longest_drop"] = int((en_ - st_).max()) if len(st_) else 0
    else:
        s["longest_drop"] = 0
    use = m.copy()
    if exclude_settle and v.settle and n:
        ex = np.zeros(len(v.t), bool)
        for a, b in v.settle:
            ex |= (v.t >= a) & (v.t <= b)
        if (use & ~ex).sum() >= 5:
            use &= ~ex
    ra, dec = v.ra[use], v.dec[use]
    s["n_rms"] = int(use.sum())
    s["rms_ra"], s["rms_dec"] = _rms(ra), _rms(dec)
    s["rms_tot"] = math.hypot(s["rms_ra"], s["rms_dec"]) if n else float("nan")
    s["peak"] = float(max(np.abs(ra).max(), np.abs(dec).max())) if len(ra) else float("nan")
    s["snr_med"] = float(np.median(v.snr[m])) if n else float("nan")
    s["snr_min"] = float(np.min(v.snr[m])) if n else float("nan")
    if v.has_pulse and n:
        rp, dp = np.abs(v.rap[m]), np.abs(v.decp[m])
        s["pulse_frac"] = float(np.mean((rp > 0) | (dp > 0))) * 100
        s["at_limit"] = int(((rp >= PULSE_LIMIT_MS) | (dp >= PULSE_LIMIT_MS)).sum())
    else:
        s["pulse_frac"], s["at_limit"] = None, None
    def _cnt(kind):
        ts = [t for t, k, _ in v.events if k == kind]
        return int(sel_mask(ts, t0, t1, sel, mode).sum()) if ts else 0
    s["dithers"], s["settle_ok"], s["settle_fail"] = _cnt("dither"), _cnt("settle_ok"), _cnt("settle_fail")
    s["lost"] = int(sel_mask(v.lost_t, t0, t1, sel, mode).sum())
    mh = sel_mask(v.hfd_t, t0, t1, sel, mode)
    h = v.hfd[mh]
    s["hfd_n"] = int(len(h))
    if len(h):
        s.update(hfd_min=float(h.min()), hfd_max=float(h.max()), hfd_med=float(np.median(h)),
                 hfd_mean=float(h.mean()), hfd_std=float(h.std()))
    s["af"] = [r for r in v.af if r.end >= t0 and r.start <= t1]
    return s


def session_rows(v: View, exclude_settle=True):
    rows = []
    for ss in v.sessions:
        st = compute_stats(v, ss.start, ss.end, exclude_settle)
        rows.append((ss, st))
    return rows


def fmt_clock(t: float, with_date=False) -> str:
    d = datetime.fromtimestamp(t, tz=timezone.utc)
    return d.strftime("%d.%m. %H:%M:%S" if with_date else "%H:%M:%S")


def fmt_dur(sec: float) -> str:
    sec = int(round(sec))
    return "%d:%02d:%02d" % (sec // 3600, sec % 3600 // 60, sec % 60) if sec >= 3600 else \
        "%d:%02d" % (sec // 60, sec % 60)


def summary_text(v: View, exclude_settle=True) -> str:
    out = []
    if v.head:
        out.append(" | ".join(v.head))
    out.append("Pixel scale: %.2f arcsec/px · Quelle: %s" % (v.scale, v.src or "-"))
    out.append("Nr  Start          Ende      Dauer  Seite  Frames  Drop%   RMS\"  Dither  Fehl.  HFR~")
    for ss, st in session_rows(v, exclude_settle):
        hfr = "-"
        mh = (v.hfd_t >= ss.start) & (v.hfd_t <= ss.end)
        if mh.any():
            hfr = "%.2f" % (np.median(v.hfd[mh]) / 2)
        out.append("%2d  %s  %s  %6s  %-5s %6d  %5.1f  %6.2f  %5d  %5d  %s" % (
            ss.nr, fmt_clock(ss.start, True), fmt_clock(ss.end), fmt_dur(ss.end - ss.start),
            ss.pier or "-", st["n"] + st["ndrop"], st["drop_pct"],
            st["rms_tot"] * v.scale if st["n"] else float("nan"),
            st["dithers"], st["settle_fail"], hfr))
    return "\n".join(out)


def export_csv(v: View, t0: float, t1: float, path: str, sel=None, mode: str = "keep"):
    m = sel_mask(v.t, t0, t1, sel, mode)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(tr("csv_cols").split(","))
        for i in np.where(m)[0]:
            w.writerow([datetime.fromtimestamp(v.t[i], tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                        "", "%.3f" % v.ra[i], "%.3f" % v.dec[i],
                        "%.3f" % (v.ra[i] * v.scale), "%.3f" % (v.dec[i] * v.scale),
                        "" if np.isnan(v.rap[i]) else "%d" % v.rap[i],
                        "" if np.isnan(v.decp[i]) else "%d" % v.decp[i],
                        "%.1f" % v.snr[i], "%d" % v.mass[i]])


# --------------------------------------------------------------------------- plot
COL_RA, COL_DEC = "#2b6cb0", "#c53030"
COL_DROP, COL_DITHER, COL_HFD, COL_AF = "#dd6b20", "#2f855a", "#2f855a", "#805ad5"


def _gaps(t, *arrs, gap=40.0):
    """Fuegt NaN bei Zeitluecken ein, damit Linien dort unterbrochen werden."""
    t = np.asarray(t, float)
    if len(t) < 2:
        return (t,) + tuple(np.asarray(a, float) for a in arrs)
    idx = np.nonzero(np.diff(t) > gap)[0] + 1
    out = [np.insert(t, idx, np.nan)]
    for a in arrs:
        out.append(np.insert(np.asarray(a, float), idx, np.nan))
    return tuple(out)


class GuidePlot:
    """Diagramm-Logik ohne Tk-Abhaengigkeit: Zeichnen, Zoom, Pan, Bereichsauswahl."""

    def __init__(self, fig, on_view=None, schedule=None):
        self.fig = fig
        self.on_view = on_view
        self.schedule = schedule or (lambda f: f())
        self.view = None
        self.opt = {}
        self.ax = {}
        self.full = (0.0, 1.0)
        self.y_auto = True
        self._pan = None
        self._pending = False
        self._span = None
        self._cids = []
        self.sel = []            # markierte Zeitbereiche [(a,b)] in Sekunden
        self.sel_mode = "keep"   # 'keep' = nur Auswahl, 'drop' = Auswahl ausschliessen
        self._sel_art = []
        self._connect()

    # -- Ereignisse -----------------------------------------------------------
    def _connect(self):
        c = self.fig.canvas
        self._cids = [c.mpl_connect("scroll_event", self._on_scroll),
                      c.mpl_connect("button_press_event", self._on_press),
                      c.mpl_connect("button_release_event", self._on_release),
                      c.mpl_connect("motion_notify_event", self._on_motion),
                      c.mpl_connect("key_press_event", self._on_key)]

    def _main_axes(self):
        return [a for a in self.ax.values()] if self.ax else []

    def _on_scroll(self, e):
        if e.inaxes not in self._main_axes() or e.xdata is None:
            return
        f = 0.8 if e.button == "up" else 1.25
        if e.key == "control" and e.inaxes is self.ax.get("err"):
            lo, hi = e.inaxes.get_ylim()
            c = e.ydata
            self.y_auto = False
            e.inaxes.set_ylim(c - (c - lo) * f, c + (hi - c) * f)
            self.fig.canvas.draw_idle()
            return
        self.zoom(f, e.xdata * 86400.0)

    def _on_press(self, e):
        if e.inaxes not in self._main_axes():
            return
        if getattr(e, "dblclick", False) and e.button == 1:
            self.reset()
            return
        if e.button == 1:
            a, b = self.get_xlim()
            self._pan = (e.x, a, b)

    def _on_release(self, e):
        self._pan = None

    def _on_motion(self, e):
        if self._pan is None or e.x is None:
            return
        x0, a, b = self._pan
        axp = self.ax["err"]
        width = max(axp.bbox.width, 1.0)
        dx = (x0 - e.x) * (b - a) / width
        self.set_xlim(a + dx, b + dx)

    def _on_key(self, e):
        if e.key == "escape":
            self.clear_sel()
        elif e.key in ("home", "r"):
            self.reset()
        elif e.key == "left":
            self.pan_by(-0.25)
        elif e.key == "right":
            self.pan_by(0.25)
        elif e.key in ("+", "="):
            self.zoom(0.7)
        elif e.key == "-":
            self.zoom(1.4)

    def _on_span(self, xmin, xmax):
        a, b = xmin * 86400.0, xmax * 86400.0
        if b - a < 4.0:                       # Klick ohne Ziehen: Bereich unter dem Zeiger entfernen
            c = (a + b) / 2
            keep = [r for r in self.sel if not (r[0] <= c <= r[1])]
            if len(keep) != len(self.sel):
                self.sel = keep
                self._sel_changed()
            return
        self.sel = self._merge(self.sel + [(a, b)])
        self._sel_changed()

    @staticmethod
    def _merge(rs):
        out = []
        for a, b in sorted(rs):
            if out and a <= out[-1][1]:
                out[-1] = (out[-1][0], max(out[-1][1], b))
            else:
                out.append((a, b))
        return out

    def clear_sel(self):
        if self.sel:
            self.sel = []
            self._sel_changed()

    def set_sel_mode(self, mode):
        self.sel_mode = mode
        self._sel_changed()

    def _sel_changed(self):
        self._draw_sel()
        if self.ax:
            self._update_dynamic()

    def _draw_sel(self):
        for art in self._sel_art:
            try:
                art.remove()
            except (ValueError, NotImplementedError):
                pass
        self._sel_art = []
        col = "#ed8936" if self.sel_mode == "keep" else "#e53e3e"
        for a, b in self.sel:
            for ax in self.ax.values():
                self._sel_art.append(ax.axvspan(a / 86400.0, b / 86400.0, color=col, alpha=0.22, lw=0,
                                                zorder=1.5))
        self.fig.canvas.draw_idle()

    # -- Ansichtssteuerung (Sekunden) -------------------------------------------
    def get_xlim(self):
        a, b = self.ax["err"].get_xlim()
        return a * 86400.0, b * 86400.0

    def set_xlim(self, a, b):
        lo, hi = self.full
        full = max(hi - lo, 1.0)
        span = b - a
        if span < 15:
            c = (a + b) / 2
            a, b = c - 7.5, c + 7.5
            span = 15
        if span > full * 1.3:
            a, b = lo - 0.02 * full, hi + 0.02 * full
            span = b - a
        if a < lo - 0.15 * full:
            a, b = lo - 0.15 * full, lo - 0.15 * full + span
        if b > hi + 0.15 * full:
            a, b = hi + 0.15 * full - span, hi + 0.15 * full
        self.ax["err"].set_xlim(a / 86400.0, b / 86400.0)
        self.fig.canvas.draw_idle()

    def zoom(self, f, center=None):
        if not self.ax:
            return
        a, b = self.get_xlim()
        c = (a + b) / 2 if center is None else center
        self.set_xlim(c - (c - a) * f, c + (b - c) * f)

    def pan_by(self, frac):
        if not self.ax:
            return
        a, b = self.get_xlim()
        d = (b - a) * frac
        self.set_xlim(a + d, b + d)

    def reset(self):
        if self.ax:
            lo, hi = self.full
            pad = max((hi - lo) * 0.01, 5)
            self.y_auto = True
            self.set_xlim(lo - pad, hi + pad)

    def goto(self, a, b, pad=0.04):
        if self.ax:
            p = max((b - a) * pad, 10)
            self.set_xlim(a - p, b + p)

    # -- Zeichnen ------------------------------------------------------------------
    def render(self, view, opt):
        import matplotlib.dates as mdates
        from matplotlib.widgets import SpanSelector
        self.view, self.opt = view, dict(opt)
        fig = self.fig
        fig.clf()
        self.ax = {}
        self._span = None
        unit_as = opt.get("unit", "arcsec") == "arcsec"
        k = view.scale if unit_as else 1.0
        self._ra, self._dec = view.ra * k, view.dec * k
        self._k = k
        self.full = (view.t0, view.t1)
        rows = ["err"]
        if opt.get("show_pulses", True):
            rows.append("pulse")
        if opt.get("show_star", True):
            rows.append("star")
        ratios = {"err": 3.2, "pulse": 1.1, "star": 1.5}
        gs = fig.add_gridspec(len(rows), 2, width_ratios=[7, 1], height_ratios=[ratios[r] for r in rows],
                              hspace=0.07, wspace=0.03, left=0.065, right=0.985, top=0.975, bottom=0.075)
        first = None
        for i, r in enumerate(rows):
            ax = fig.add_subplot(gs[i, 0], sharex=first) if first is not None else fig.add_subplot(gs[i, 0])
            first = first or ax
            self.ax[r] = ax
            ax.grid(True, alpha=0.25, lw=0.5)
            ax.tick_params(labelsize=8, labelbottom=(i == len(rows) - 1))
        self.hist = {}
        if "err" in rows:
            self.hist["err"] = fig.add_subplot(gs[rows.index("err"), 1])
        if "star" in rows:
            self.hist["star"] = fig.add_subplot(gs[rows.index("star"), 1])
        if "pulse" in rows:
            off = fig.add_subplot(gs[rows.index("pulse"), 1])
            off.axis("off")
        bottom = self.ax[rows[-1]]
        loc = mdates.AutoDateLocator(minticks=4, maxticks=9)
        bottom.xaxis.set_major_locator(loc)
        bottom.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc))
        e = self.ax["err"]
        # Sitzungen: abwechselnd leicht eingefaerbt, Nummer oben
        for i, ss in enumerate(view.sessions):
            for a in self.ax.values():
                a.axvspan(ss.start / 86400.0, ss.end / 86400.0, color="#edf2f7" if i % 2 == 0 else "#fffaf0",
                          lw=0, zorder=0)
            e.text((ss.start + ss.end) / 2 / 86400.0, 1.005, str(ss.nr), transform=e.get_xaxis_transform(),
                   ha="center", va="bottom", fontsize=7, color="#555", clip_on=True)
        if opt.get("show_events", True):
            cb = [t for t, kd, _ in view.events if kd == "calib_begin"]
            ce = [t for t, kd, _ in view.events if kd == "calib_end"]
            for a_, b_ in zip(cb, ce):
                for a in self.ax.values():
                    a.axvspan(a_ / 86400.0, b_ / 86400.0, color="#fefcbf", alpha=0.7, lw=0, zorder=0)
            ends = [t / 86400.0 for t, kd, _ in view.events if kd == "end"]
            for a in self.ax.values():
                if ends:
                    a.vlines(ends, 0, 1, transform=a.get_xaxis_transform(), colors="#718096",
                             linestyles="--", lw=0.7)
            sf = [t / 86400.0 for t, kd, _ in view.events if kd == "settle_fail"]
            if sf:
                e.plot(sf, [0.955] * len(sf), "x", color="#e53e3e", ms=5, mew=1.3,
                       transform=e.get_xaxis_transform(), scalex=False, scaley=False, label=tr("settle_fail"))
            for r in view.af:
                for a in self.ax.values():
                    a.axvspan(r.start / 86400.0, r.end / 86400.0, color=COL_AF, alpha=0.16, lw=0, zorder=0)
        if opt.get("show_dither", True):
            dth = [t / 86400.0 for t, kd, _ in view.events if kd == "dither"]
            for a in self.ax.values():
                if dth:
                    a.vlines(dth, 0, 1, transform=a.get_xaxis_transform(), colors=COL_DITHER,
                             linestyles=":", lw=0.8)
            if dth:
                e.plot([], [], ":", color=COL_DITHER, label=tr("dither"))
        gt, gra, gdec, grap, gdecp, gsnr = _gaps(view.t, self._ra, self._dec, view.rap, view.decp, view.snr)
        gt = gt / 86400.0
        if opt.get("show_ra", True):
            e.plot(gt, gra, "-", lw=0.8, color=COL_RA, label=tr("ra"))
        if opt.get("show_dec", True):
            e.plot(gt, gdec, "-", lw=0.8, color=COL_DEC, label=tr("dec"))
        if opt.get("show_drops", True) and len(view.dt):
            e.vlines(view.dt / 86400.0, 0, 0.045, transform=e.get_xaxis_transform(), colors=COL_DROP, lw=0.6)
            e.plot([], [], "|", color=COL_DROP, label=tr("drops"))
        e.axhline(0, color="#4a5568", lw=0.6)
        e.set_ylabel(tr("err_ylabel_as" if unit_as else "err_ylabel_px"), fontsize=8)
        e.legend(loc="upper right", ncol=6, fontsize=7, framealpha=0.85)

        if "pulse" in self.ax:
            p = self.ax["pulse"]
            if view.has_pulse:
                p.plot(gt, grap, drawstyle="steps-mid", lw=0.6, color=COL_RA)
                p.plot(gt, gdecp, drawstyle="steps-mid", lw=0.6, color=COL_DEC)
                p.axhline(2500, color="#a0aec0", ls=":", lw=0.7)
                p.axhline(-2500, color="#a0aec0", ls=":", lw=0.7)
                p.set_ylim(-2800, 2800)
            else:
                p.text(0.5, 0.5, tr("no_pulse"), transform=p.transAxes, ha="center", va="center",
                       fontsize=8, color="#718096")
            p.set_ylabel(tr("pulse_ylabel"), fontsize=8)

        self._hfd_mode = opt.get("hfd_mode", "hfd")
        self._hk = 0.5 if self._hfd_mode == "hfr" else 1.0
        if "star" in self.ax:
            s = self.ax["star"]
            self._star_twin = None
            if len(view.hfd_t):
                s.plot(view.hfd_t / 86400.0, view.hfd * self._hk, ".", ms=2.2, color=COL_HFD, alpha=0.8)
                s.set_ylabel(tr("hfr_ylabel" if self._hfd_mode == "hfr" else "hfd_ylabel"), fontsize=8,
                             color=COL_HFD)
                if len(view.lost_t):
                    s.vlines(view.lost_t / 86400.0, 0, 0.05, transform=s.get_xaxis_transform(),
                             colors="#e53e3e", lw=0.7)
                tw = s.twinx()
                tw.plot(gt, gsnr, "-", lw=0.6, color="#718096", alpha=0.8)
                tw.set_ylabel(tr("snr"), fontsize=8, color="#718096")
                tw.tick_params(labelsize=8)
                self._star_twin = tw
            else:
                s.plot(gt, gsnr, "-", lw=0.7, color="#718096")
                s.set_ylabel(tr("snr"), fontsize=8)
                s.text(0.5, 0.9, tr("hfd_note"), transform=s.transAxes, ha="center", va="top",
                       fontsize=8, color="#718096")
            for r in view.af:
                s.text(r.start / 86400.0, 0.92, "AF", transform=s.get_xaxis_transform(), fontsize=7,
                       color=COL_AF, ha="left", va="top", clip_on=True)
        for h in self.hist.values():
            h.tick_params(labelsize=7, labelleft=False, labelbottom=False)
        e.callbacks.connect("xlim_changed", self._xlim_changed)
        try:
            self._span = SpanSelector(e, self._on_span, "horizontal", useblit=False, button=3,
                                      props=dict(alpha=0.25, facecolor="#3182ce"))
        except TypeError:
            self._span = SpanSelector(e, self._on_span, "horizontal", useblit=False, button=3)
        self._sel_art = []
        self._draw_sel()
        self.reset()
        self._update_dynamic()

    # -- dynamische Teile: Y-Skalierung, Histogramme, Statistik --------------------
    def _xlim_changed(self, _ax=None):
        if self._pending:
            return
        self._pending = True
        self.schedule(self._update_dynamic)

    def _update_dynamic(self):
        self._pending = False
        if not self.ax or self.view is None:
            return
        v = self.view
        a, b = self.get_xlim()
        m = (v.t >= a) & (v.t <= b)                     # sichtbar (fuer Y-Skala)
        ms = sel_mask(v.t, a, b, self.sel, self.sel_mode)  # Auswahl (fuer Histogramme)
        e = self.ax["err"]
        mv = ms if self.sel else m                       # Y-Skala folgt der Auswahl
        vals = []
        if self.opt.get("show_ra", True):
            vals.append(self._ra[mv])
        if self.opt.get("show_dec", True):
            vals.append(self._dec[mv])
        vals = np.concatenate(vals) if vals else np.zeros(0)
        vals = vals[np.isfinite(vals)]
        if self.y_auto and len(vals):
            lim = float(np.percentile(np.abs(vals), 99.5)) * 1.25
            lim = max(lim, 0.8 if self._k != 1.0 else 0.5)
            e.set_ylim(-lim, lim)
        if "err" in self.hist:
            h = self.hist["err"]
            h.clear()
            h.tick_params(labelsize=7, labelleft=False, labelbottom=False)
            lo, hi = e.get_ylim()
            if len(vals) > 3:
                for arr, col, on in ((self._ra[ms], COL_RA, self.opt.get("show_ra", True)),
                                     (self._dec[ms], COL_DEC, self.opt.get("show_dec", True))):
                    if on and len(arr):
                        h.hist(arr, bins=np.linspace(lo, hi, 31), orientation="horizontal",
                               color=col, alpha=0.55, lw=0)
            h.set_ylim(lo, hi)
        if "star" in self.ax:
            s = self.ax["star"]
            mh = sel_mask(v.hfd_t, a, b, self.sel, self.sel_mode)
            hv = v.hfd[mh] * self._hk
            if len(hv):
                top = float(np.percentile(hv, 99.5)) * 1.2
                s.set_ylim(0, max(top, 0.5))
                if "star" in self.hist:
                    h = self.hist["star"]
                    h.clear()
                    h.tick_params(labelsize=7, labelleft=False, labelbottom=False)
                    h.hist(hv, bins=np.linspace(0, max(top, 0.5), 26), orientation="horizontal",
                           color=COL_HFD, alpha=0.7, lw=0)
                    h.set_ylim(*s.get_ylim())
                if self._star_twin is not None:
                    sm = v.snr[m]
                    if len(sm):
                        self._star_twin.set_ylim(0, float(np.percentile(sm, 99.5)) * 1.2 + 1)
            elif "star" in self.hist:
                self.hist["star"].clear()
                self.hist["star"].axis("off")
                sm = v.snr[m]
                if len(sm) and self._star_twin is None:
                    s.set_ylim(0, float(np.percentile(sm, 99.5)) * 1.2 + 1)
        self.fig.canvas.draw_idle()
        if self.on_view:
            self.on_view(a, b)

    # -- Mauszeiger-Info -----------------------------------------------------------
    def info_at(self, xdata):
        v = self.view
        if v is None or not len(v.t) or xdata is None:
            return ""
        t = xdata * 86400.0
        i = int(np.clip(np.searchsorted(v.t, t), 1, len(v.t) - 1))
        if abs(v.t[i - 1] - t) < abs(v.t[i] - t):
            i -= 1
        sc = v.scale
        s = "%s | RA %+.2f″ Dec %+.2f″ | SNR %.0f" % (fmt_clock(v.t[i], True), v.ra[i] * sc, v.dec[i] * sc, v.snr[i])
        if len(v.hfd_t):
            j = int(np.clip(np.searchsorted(v.hfd_t, t), 1, max(len(v.hfd_t) - 1, 1)))
            if j < len(v.hfd_t) and abs(v.hfd_t[j] - t) < 30:
                s += " | HFD %.2f / HFR %.2f" % (v.hfd[j], v.hfd[j] / 2)
        return s


# ------------------------------------------------------------------------ stats text
def format_stats(v: View, st: dict, unit="arcsec", hfd_mode="hfd") -> str:
    sc = v.scale
    L = []
    if st.get("nsel"):
        L.append("%s: %s" % (tr("sel_title"), tr("sel_keep_info" if st["sel_mode"] == "keep" else "sel_drop_info",
                                                 st["nsel"], fmt_dur(st["sel_dur"]))))
    L.append("%s: %s – %s (%s)" % (tr("range"), fmt_clock(st["t0"], True), fmt_clock(st["t1"]),
                                    fmt_dur(st["t1"] - st["t0"])))
    tot = st["n"] + st["ndrop"]
    L.append("%s: %d  (%s %d = %.1f %%, %s %d)" % (tr("frames_line"), tot, tr("dropped"), st["ndrop"],
                                                  st["drop_pct"], tr("longest"), st["longest_drop"]))
    if st["n"]:
        r = (st["rms_ra"], st["rms_dec"], st["rms_tot"])
        L.append("%s:" % tr("rms_line"))
        L.append("   %.2f / %.2f / %.2f px" % r)
        L.append("   %.2f / %.2f / %.2f ″" % tuple(x * sc for x in r))
        L.append("%s: %.2f px = %.2f ″" % (tr("peak_line"), st["peak"], st["peak"] * sc))
        L.append("%s: %.0f / %.0f" % (tr("snr_line"), st["snr_min"], st["snr_med"]))
        if st["pulse_frac"] is not None:
            L.append("%s: %.0f %%" % (tr("pulse_line"), st["pulse_frac"]))
            L.append("%s: %d" % (tr("limit_line"), st["at_limit"]))
    L.append("%s: %d    %s: %d / %d" % (tr("dither_line"), st["dithers"], tr("settle_line"),
                                         st["settle_ok"], st["settle_fail"]))
    L.append("%s: %d" % (tr("lost_line"), st["lost"]))
    L.append("")
    L.append(tr("hfd_title"))
    if st["hfd_n"]:
        L.append("%s: %d" % (tr("hfd_n"), st["hfd_n"]))
        L.append("%s: %.2f / %.2f" % (tr("hfd_minmax"), st["hfd_min"], st["hfd_max"]))
        L.append("%s: %.2f / %.2f" % (tr("hfd_med"), st["hfd_med"], st["hfd_mean"]))
        L.append("%s: %.2f" % (tr("hfd_std"), st["hfd_std"]))
        L.append("%s: %.2f" % (tr("hfr_med"), st["hfd_med"] / 2))
    else:
        L.append(tr("hfd_none"))
    if st["af"]:
        L.append("")
        L.append("%s: %d" % (tr("af_title"), len(st["af"])))
        for r in st["af"][:6]:
            res = tr("af_open") if r.code is None else (tr("af_ok") if r.code == 0 else tr("af_err", r.code))
            best = ""
            if r.best and r.best[1] is not None:
                best = "  pos %s  HFR %.2f" % (int(r.best[0]) if r.best[0] is not None else "?", r.best[1])
            L.append("  %s  %s%s" % (fmt_clock(r.start), res, best))
    return "\n".join(L)


# --------------------------------------------------------------------------- config
CFG_PATH = os.path.join(os.path.expanduser("~"), ".stellavitalogsreader.json")


def load_cfg() -> dict:
    try:
        with open(CFG_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_cfg(cfg: dict):
    try:
        with open(CFG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh)
    except OSError:
        pass


def load_paths(paths, progress=None) -> LogData:
    d = LogData()
    for p in paths:
        if progress:
            progress(os.path.basename(p))
        with open(p, "rb") as fh:
            d.add_file(os.path.basename(p), fh.read())
    return d


# ----------------------------------------------------------------------------- GUI
def run_gui(files=None, mainloop=True):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

    class App(tk.Tk):
        def __init__(self, files):
            super().__init__()
            self.cfg = load_cfg()
            global LANG
            LANG = self.cfg.get("lang", "de")
            self.geometry("1380x820")
            self.data = None
            self.view = None
            self.q = queue.Queue()
            self.var = {
                "offset": tk.DoubleVar(value=DEFAULT_BOX_OFFSET_H),
                "unit": tk.StringVar(value="arcsec"),
                "hfd_mode": tk.StringVar(value="hfd"),
                "show_ra": tk.BooleanVar(value=True),
                "show_dec": tk.BooleanVar(value=True),
                "show_drops": tk.BooleanVar(value=True),
                "show_dither": tk.BooleanVar(value=True),
                "show_events": tk.BooleanVar(value=True),
                "show_pulses": tk.BooleanVar(value=True),
                "show_star": tk.BooleanVar(value=True),
                "y_auto": tk.BooleanVar(value=True),
                "excl": tk.BooleanVar(value=True),
                "sel_mode": tk.StringVar(value="keep"),
            }
            try:  # scharfe Darstellung unter Windows
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(1)
            except Exception:
                pass
            self._build_ui()
            if files:
                self.after(200, lambda: self.load(files))

        # -- Aufbau --------------------------------------------------------------------
        def _build_ui(self):
            self.title(tr("title"))
            menubar = tk.Menu(self)
            fm = tk.Menu(menubar, tearoff=0)
            fm.add_command(label=tr("open_files"), command=self.open_files)
            fm.add_command(label=tr("open_folder"), command=self.open_folder)
            fm.add_separator()
            fm.add_command(label=tr("save_decoded"), command=self.save_decoded)
            fm.add_command(label=tr("export_csv"), command=self.export_csv)
            fm.add_command(label=tr("png"), command=self.save_png)
            fm.add_separator()
            fm.add_command(label=tr("quit"), command=self.destroy)
            menubar.add_cascade(label=tr("menu_file"), menu=fm)
            lm = tk.Menu(menubar, tearoff=0)
            lm.add_command(label="Deutsch", command=lambda: self.set_lang("de"))
            lm.add_command(label="English", command=lambda: self.set_lang("en"))
            menubar.add_cascade(label=tr("menu_lang"), menu=lm)
            hm = tk.Menu(menubar, tearoff=0)
            hm.add_command(label=tr("about"), command=lambda: messagebox.showinfo(
                tr("about"), tr("about_text", __version__)))
            menubar.add_cascade(label=tr("menu_help"), menu=hm)
            self.config(menu=menubar)

            top = ttk.Frame(self, padding=(6, 4))
            top.pack(side="top", fill="x")
            ttk.Button(top, text=tr("open_files"), command=self.open_files).pack(side="left")
            ttk.Button(top, text=tr("open_folder"), command=self.open_folder).pack(side="left", padx=(4, 12))
            ttk.Label(top, text=tr("offset")).pack(side="left")
            sp = ttk.Spinbox(top, from_=-12, to=12, increment=0.5, width=5, textvariable=self.var["offset"],
                             command=self.refresh_view)
            sp.pack(side="left", padx=(2, 2))
            sp.bind("<Return>", lambda e: self.refresh_view())
            ttk.Button(top, text=tr("auto"), width=5, command=self.auto_offset).pack(side="left", padx=(0, 12))
            ttk.Label(top, text=tr("unit")).pack(side="left")
            for val, key in (("arcsec", "arcsec"), ("px", "px")):
                ttk.Radiobutton(top, text=tr(key), value=val, variable=self.var["unit"],
                                command=self.redraw).pack(side="left")
            ttk.Label(top, text="  " + tr("starmode")).pack(side="left")
            for val in ("hfd", "hfr"):
                ttk.Radiobutton(top, text=val.upper(), value=val, variable=self.var["hfd_mode"],
                                command=self.redraw).pack(side="left")
            row2 = ttk.Frame(self, padding=(6, 0, 6, 4))
            row2.pack(side="top", fill="x")
            ttk.Label(row2, text=tr("show")).pack(side="left")
            for key in ("ra", "dec", "drops", "dither", "events", "pulses", "starpanel"):
                vk = {"pulses": "show_pulses", "starpanel": "show_star"}.get(key, "show_" + key)
                ttk.Checkbutton(row2, text=tr(key), variable=self.var[vk], command=self.redraw).pack(side="left", padx=3)
            ttk.Checkbutton(row2, text=tr("yauto"), variable=self.var["y_auto"],
                            command=self.toggle_yauto).pack(side="left", padx=(12, 3))
            ttk.Checkbutton(row2, text=tr("excl"), variable=self.var["excl"],
                            command=self.refresh_tables).pack(side="left", padx=3)
            row3 = ttk.Frame(self, padding=(6, 0, 6, 4))
            row3.pack(side="top", fill="x")
            ttk.Label(row3, text=tr("sel_title") + ":", font=("", 9, "bold")).pack(side="left")
            for val in ("keep", "drop"):
                ttk.Radiobutton(row3, text=tr("mode_" + val), value=val, variable=self.var["sel_mode"],
                                command=lambda: self.plot.set_sel_mode(self.var["sel_mode"].get())
                                ).pack(side="left", padx=4)
            ttk.Button(row3, text=tr("clear_sel"), command=lambda: self.plot.clear_sel()).pack(side="left", padx=(10, 4))
            ttk.Button(row3, text=tr("show_data"), command=self.show_data).pack(side="left", padx=4)

            self.status = tk.StringVar(value=tr("hint"))
            ttk.Label(self, textvariable=self.status, anchor="w", relief="sunken", padding=(6, 2)).pack(
                side="bottom", fill="x")

            main = ttk.PanedWindow(self, orient="horizontal")
            main.pack(side="top", fill="both", expand=True)
            left = ttk.Frame(main, width=430)
            center = ttk.Frame(main)
            right = ttk.Frame(main, width=330)
            main.add(left, weight=0)
            main.add(center, weight=1)
            main.add(right, weight=0)

            ttk.Label(left, text=tr("sessions"), font=("", 9, "bold")).pack(anchor="w", padx=4, pady=(4, 0))
            cols = ("nr", "start", "dur", "side", "frames", "drop", "rms", "dith", "fail")
            self.tree = ttk.Treeview(left, columns=cols, show="headings", height=11, selectmode="browse")
            heads = {"nr": ("col_nr", 28), "start": ("col_start", 92), "dur": ("col_dur", 52),
                     "side": ("col_side", 44), "frames": ("col_frames", 50), "drop": ("col_drop", 48),
                     "rms": ("col_rms", 44), "dith": ("col_dith", 40), "fail": ("col_fail", 36)}
            for c in cols:
                self.tree.heading(c, text=tr(heads[c][0]))
                self.tree.column(c, width=heads[c][1], anchor="center", stretch=False)
            self.tree.tag_configure("bad", background="#fed7d7")
            self.tree.tag_configure("warn", background="#fefcbf")
            self.tree.pack(fill="x", padx=4)
            self.tree.bind("<<TreeviewSelect>>", self.on_session)
            ttk.Label(left, text=tr("afruns"), font=("", 9, "bold")).pack(anchor="w", padx=4, pady=(8, 0))
            self.aftree = ttk.Treeview(left, columns=("start", "res", "pos", "hfr", "pts"), show="headings",
                                       height=7, selectmode="browse")
            for c, (h, w) in {"start": ("col_start", 92), "res": ("col_res", 80), "pos": ("col_pos", 70),
                              "hfr": ("HFR", 50), "pts": ("col_pts", 50)}.items():
                self.aftree.heading(c, text=tr(h))
                self.aftree.column(c, width=w, anchor="center", stretch=False)
            self.aftree.pack(fill="x", padx=4)
            self.aftree.bind("<<TreeviewSelect>>", self.on_af)

            self.fig = Figure(figsize=(9, 6), dpi=100)
            self.canvas = FigureCanvasTkAgg(self.fig, master=center)
            self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
            self.plot = GuidePlot(self.fig, on_view=self.on_view, schedule=lambda f: self.after(60, f))
            self.canvas.mpl_connect("motion_notify_event", self.on_hover)
            nav = ttk.Frame(center)
            nav.pack(side="bottom", fill="x")
            for txt, cmd in (("reset", self.plot.reset), ("zoom_out", lambda: self.plot.zoom(1.4)),
                             ("zoom_in", lambda: self.plot.zoom(0.7)),
                             ("◀", lambda: self.plot.pan_by(-0.3)), ("▶", lambda: self.plot.pan_by(0.3))):
                ttk.Button(nav, text=tr(txt) if txt in _TR else txt, width=7 if txt == "reset" else 3,
                           command=cmd).pack(side="left", padx=2, pady=2)
            ttk.Button(nav, text=tr("png"), command=self.save_png).pack(side="right", padx=2)

            ttk.Label(right, text=tr("stats"), font=("", 9, "bold")).pack(anchor="w", padx=4, pady=(4, 2))
            self.text = tk.Text(right, width=44, height=40, font=("Consolas", 9), wrap="none", relief="flat",
                                background="#f7fafc")
            self.text.pack(fill="both", expand=True, padx=4, pady=2)

        def set_lang(self, lang):
            global LANG
            self.cfg["lang"] = lang
            save_cfg(self.cfg)
            LANG = lang
            for w in list(self.winfo_children()):
                w.destroy()
            self._build_ui()
            self.apply_data()

        # -- Dateien -------------------------------------------------------------------
        def open_files(self):
            ps = filedialog.askopenfilenames(initialdir=self.cfg.get("dir", ""),
                                             filetypes=[("Logs", "*.txt *.log"), ("*", "*.*")])
            if ps:
                self.cfg["dir"] = os.path.dirname(ps[0])
                save_cfg(self.cfg)
                self.load(list(ps))

        def open_folder(self):
            d = filedialog.askdirectory(initialdir=self.cfg.get("dir", ""))
            if d:
                self.cfg["dir"] = d
                save_cfg(self.cfg)
                ps = sorted(os.path.join(d, f) for f in os.listdir(d)
                            if f.lower().endswith((".txt", ".log")) and
                            (f.startswith("GuideLog") or f.startswith("Logs_App")))
                if ps:
                    self.load(ps)

        def load(self, paths):
            self.status.set(tr("loading", os.path.basename(paths[0]) + (" …" if len(paths) > 1 else "")))
            self.update_idletasks()
            threading.Thread(target=self._worker, args=(paths,), daemon=True).start()
            self.after(150, self._poll)

        def _worker(self, paths):
            try:
                self.q.put(("ok", load_paths(paths)))
            except Exception as ex:  # noqa: BLE001
                self.q.put(("err", ex))

        def _poll(self):
            try:
                kind, res = self.q.get_nowait()
            except queue.Empty:
                self.after(150, self._poll)
                return
            if kind == "err":
                messagebox.showerror(tr("err"), str(res))
                return
            self.data = res
            self.plot.sel = []
            sug = res.suggest_offset()
            if sug is not None:
                self.var["offset"].set(sug)
            self.apply_data()

        def apply_data(self):
            if self.data is None:
                return
            bad = [n for n, a, _ in self.data.files if a == "?"]
            self.refresh_view()
            v = self.view
            msg = tr("loaded", len(self.data.files), len(v.t), len(v.dt), len(v.sessions))
            if bad:
                msg += " · " + tr("unknown_file", ", ".join(bad))
            if not len(v.t):
                msg = tr("nodata") + (" " + " | ".join(v.head) if v.head else "")
            self.status.set(msg)

        def auto_offset(self):
            if self.data is None:
                return
            sug = self.data.suggest_offset()
            if sug is None:
                self.status.set(tr("offset_none"))
                return
            self.var["offset"].set(sug)
            self.status.set(tr("offset_auto", sug))
            self.refresh_view()

        # -- Anzeige -------------------------------------------------------------------
        def opts(self):
            o = {k: v.get() for k, v in self.var.items() if k not in ("offset",)}
            o["unit"] = self.var["unit"].get()
            return o

        def refresh_view(self):
            if self.data is None:
                return
            try:
                off = float(self.var["offset"].get())
            except (ValueError, tk.TclError):
                off = DEFAULT_BOX_OFFSET_H
            self.view = self.data.build_view(off)
            self.redraw()
            self.refresh_tables()

        def redraw(self):
            if self.view is None:
                return
            self.plot.render(self.view, self.opts())
            self.canvas.draw_idle()

        def toggle_yauto(self):
            self.plot.y_auto = bool(self.var["y_auto"].get())
            self.plot._update_dynamic()

        def refresh_tables(self):
            if self.view is None:
                return
            v = self.view
            self.tree.delete(*self.tree.get_children())
            for ss, st in session_rows(v, self.var["excl"].get()):
                tag = ()
                if st["drop_pct"] > 30 or st["settle_fail"] > 0:
                    tag = ("bad",)
                elif st["drop_pct"] > 10:
                    tag = ("warn",)
                rms = "%.2f" % (st["rms_tot"] * v.scale) if st["n"] > 3 and not math.isnan(st["rms_tot"]) else "–"
                self.tree.insert("", "end", iid=str(ss.nr - 1), tags=tag, values=(
                    ss.nr, fmt_clock(ss.start, True), fmt_dur(ss.end - ss.start), ss.pier or "–",
                    st["n"] + st["ndrop"], "%.0f" % st["drop_pct"], rms, st["dithers"], st["settle_fail"]))
            self.aftree.delete(*self.aftree.get_children())
            for i, r in enumerate(v.af):
                res = tr("af_open") if r.code is None else (tr("af_ok") if r.code == 0 else tr("af_err", r.code))
                pos = int(r.best[0]) if r.best and r.best[0] is not None else "–"
                hfr = "%.2f" % r.best[1] if r.best and r.best[1] is not None else "–"
                self.aftree.insert("", "end", iid=str(i), values=(
                    fmt_clock(r.start, True), res, pos, hfr, len(r.pts)))

        def on_session(self, _e=None):
            sel = self.tree.selection()
            if sel and self.view is not None:
                ss = self.view.sessions[int(sel[0])]
                self.plot.goto(ss.start, ss.end)

        def on_af(self, _e=None):
            sel = self.aftree.selection()
            if sel and self.view is not None:
                r = self.view.af[int(sel[0])]
                self.plot.goto(r.start - 120, r.end + 120, 0.0)

        def on_view(self, a, b):
            if self.view is None:
                return
            st = compute_stats(self.view, a, b, self.var["excl"].get(), self.plot.sel, self.plot.sel_mode)
            txt = format_stats(self.view, st, self.var["unit"].get(), self.var["hfd_mode"].get())
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.insert("1.0", txt)
            self.text.configure(state="disabled")

        def on_hover(self, e):
            if e.inaxes is not None and self.view is not None:
                info = self.plot.info_at(e.xdata)
                if info:
                    self.status.set(info)

        # -- Export --------------------------------------------------------------------
        def show_data(self):
            """Tabelle der Frames in Auswahl (bzw. im sichtbaren Bereich) in eigenem Fenster."""
            if self.view is None:
                self.status.set(tr("no_view"))
                return
            v = self.view
            a, b = self.plot.get_xlim()
            idx = np.where(sel_mask(v.t, a, b, self.plot.sel, self.plot.sel_mode))[0]
            win = tk.Toplevel(self)
            win.title(tr("data_title"))
            win.geometry("760x480")
            cols = tr("data_cols").split(",")
            tv = ttk.Treeview(win, columns=cols, show="headings")
            for c in cols:
                tv.heading(c, text=c)
                tv.column(c, width=100 if c == cols[0] else 70, anchor="e")
            sb = ttk.Scrollbar(win, orient="vertical", command=tv.yview)
            tv.configure(yscrollcommand=sb.set)
            lim = 20000
            for i in idx[:lim]:
                f = lambda x, p="%d": "" if np.isnan(x) else p % x  # noqa: E731
                tv.insert("", "end", values=(
                    fmt_clock(v.t[i]), "%.2f" % (v.ra[i] * v.scale), "%.2f" % (v.dec[i] * v.scale),
                    "%.2f" % v.ra[i], "%.2f" % v.dec[i], f(v.rap[i]), f(v.decp[i]), "%.0f" % v.snr[i]))
            bar = ttk.Frame(win)
            bar.pack(side="bottom", fill="x")
            ttk.Label(bar, text="%d" % len(idx) + ("  " + tr("data_more", lim, len(idx)) if len(idx) > lim else "")
                      ).pack(side="left", padx=6)
            ttk.Button(bar, text=tr("export_csv"), command=self.export_csv).pack(side="right", padx=6, pady=3)
            sb.pack(side="right", fill="y")
            tv.pack(side="left", fill="both", expand=True)

        def save_decoded(self):
            if self.data is None:
                self.status.set(tr("no_view"))
                return
            d = filedialog.askdirectory(initialdir=self.cfg.get("dir", ""))
            if not d:
                return
            n = 0
            for name, text in self.data.decoded_texts():
                base, _ = os.path.splitext(name)
                with open(os.path.join(d, base + "_decoded.txt"), "w", encoding="utf-8") as fh:
                    fh.write(text)
                n += 1
            self.status.set(tr("saved", "%d × _decoded.txt" % n))

        def export_csv(self):
            if self.view is None:
                self.status.set(tr("no_view"))
                return
            p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
            if p:
                a, b = self.plot.get_xlim()
                export_csv(self.view, a, b, p, self.plot.sel, self.plot.sel_mode)
                self.status.set(tr("saved", p))

        def save_png(self):
            p = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG", "*.png")])
            if p:
                self.fig.savefig(p, dpi=150)
                self.status.set(tr("saved", p))

    app = App(files)
    if mainloop:
        app.mainloop()
    return app


# ------------------------------------------------------------------------------ CLI
def main(argv=None):
    ap = argparse.ArgumentParser(description="StellavitaLogsreader – StellaVita Guiding-Log-Viewer")
    ap.add_argument("files", nargs="*", help="GuideLog_*.txt / Logs_App_*.txt")
    ap.add_argument("--summary", action="store_true", help="nur Sitzungstabelle ausgeben (ohne Fenster)")
    ap.add_argument("--decode", action="store_true", help="eine Datei entschlüsseln: --decode IN [OUT]")
    ap.add_argument("--offset", type=float, default=None, help="Box-Zeit → Ortszeit in Stunden (Standard: Auto/-1)")
    a = ap.parse_args(argv)
    if a.decode:
        if not a.files:
            ap.error("--decode braucht eine Eingabedatei")
        with open(a.files[0], "rb") as fh:
            text, info = decode_log(fh.read())
        if text is None:
            print("Format nicht erkannt", file=sys.stderr)
            return 1
        out = a.files[1] if len(a.files) > 1 else None
        if out:
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text)
        else:
            sys.stdout.write(text)
        return 0
    if a.summary:
        d = load_paths(a.files)
        off = a.offset
        if off is None:
            off = d.suggest_offset()
            off = DEFAULT_BOX_OFFSET_H if off is None else off
        print(summary_text(d.build_view(off)))
        return 0
    run_gui(a.files or None)
    return 0


if __name__ == "__main__":
    sys.exit(main())
