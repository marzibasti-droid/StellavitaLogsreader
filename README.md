# StellavitaLogsreader – Log Viewer for StellaVita

https://github.com/marzibasti-droid/StellavitaLogsreader · License: GPL-3.0

Decodes the obfuscated StellaVita box `GuideLog_*.txt` and app `Logs_App_*.txt` files and shows a zoomable guide graph, session table, dropouts and HFD/HFR statistics.

## Start

    pip install numpy matplotlib      (optional – if missing, the program asks at startup and installs them itself)
    python stellavita_logsreader.py                      (window, then open files)
    python stellavita_logsreader.py GuideLog_*.txt Logs_App_*.txt
    python stellavita_logsreader.py --summary FILES      (table only, no window)
    python stellavita_logsreader.py --decode IN [OUT]    (decode a single file)

EXE: `build_exe.bat` (Windows) → `dist\StellavitaLogsreader.exe`

## Controls

- Mouse wheel: zoom on time · Left mouse button drag: pan
- **Right mouse button drag: mark a range** (several possible; right-click on a range removes it; Esc = clear all).
  Statistics, histograms and the Y scale then refer to the selection only. The "Exclude selection" switch calculates
  everything *except* the selection instead (e.g. to leave out settling or outliers). The "Data…" button shows the frames
  of the selection, and so does the CSV export.
- Double-click / Home / R: fit all · ← → + − : keys · Ctrl+mouse wheel: Y zoom
- Right: statistics (RMS, drop %, HFD/HFR, pulses, dithers, autofocus) **for the visible range**
- Left: sessions (red = dropouts/settle failures), autofocus runs → click jumps to the spot
- Box time offset: box logs run about 1 h ahead of app time (default −1 h, "Auto" estimates it from the app logs)
- Export: CSV (visible range), PNG, decoded text files

---

## ⚖️ Legal notice & disclaimer

**Trademark notice** – Independent open-source tool by the community, for the community. Not affiliated with, endorsed by or connected to ToupTek Astro or its partners. "ToupTek" and "StellaVita" are trademarks of their respective owners; the names are used solely to describe compatibility.

**No warranty** – The software is provided "as is", without warranty of any kind, express or implied. The author accepts no liability for hardware damage, data loss or lost astrophotography sessions. Use is entirely at your own risk.

**Privacy** – StellavitaLogsreader is a local desktop application. Log files are processed on your computer only; no log data, GPS coordinates or personal information is transmitted to or stored on any server.
**No warranty** – The software is provided "as is", without warranty of any kind, express or implied. The author
accepts no liability for hardware damage, data loss or lost imaging sessions. Use at your own risk.

**Privacy** – StellavitaLogsreader is a local desktop application. Log files are processed on your computer only; no log data,
GPS coordinates or personal information is transmitted to or stored on any server.
