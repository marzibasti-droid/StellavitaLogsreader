# StellavitaLogsreader – Log-Viewer für StellaVita / StellaVita log viewer

https://github.com/marzibasti-droid/StellavitaLogsreader · Lizenz / License: MIT

**DE** – Liest die (verschleierten) `GuideLog_*.txt` der Box und die `Logs_App_*.txt` der App, entschlüsselt sie
automatisch und zeigt Guiding-Graph (Zoom/Pan), Sitzungstabelle, Abbrüche und HFD/HFR-Statistik.

**EN** – Decodes the obfuscated StellaVita box `GuideLog_*.txt` and app `Logs_App_*.txt` files and shows a
zoomable guide graph, session table, dropouts and HFD/HFR statistics.

## Start
    pip install numpy matplotlib      (optional – fehlen sie, fragt das Programm beim Start und installiert sie selbst)
    python stellavita_logsreader.py                      (Fenster, dann Dateien öffnen)
    python stellavita_logsreader.py GuideLog_*.txt Logs_App_*.txt
    python stellavita_logsreader.py --summary DATEIEN    (nur Tabelle, ohne Fenster)
    python stellavita_logsreader.py --decode IN [OUT]    (eine Datei entschlüsseln)
EXE: `build_exe.bat` (Windows) → `dist\StellavitaLogsreader.exe`

## Bedienung / Controls
- Mausrad: Zoom auf Zeit · Linke Maustaste ziehen: Verschieben
- **Rechte Maustaste ziehen: Bereich markieren** (mehrere möglich; Rechtsklick auf einen Bereich entfernt ihn; Esc = alles löschen).
  Statistik, Histogramme und Y-Skala beziehen sich dann nur auf die Auswahl. Umschalter „Auswahl ausschließen“ rechnet
  stattdessen alles *außer* der Auswahl (z. B. Settles/Ausreißer herausnehmen). Knopf „Daten…“ zeigt die Frames der Auswahl, CSV-Export ebenso.
- Doppelklick / Home / R: alles · ← → + − : Tasten · Strg+Mausrad: Y-Zoom
- Rechts: Statistik (RMS, Drop-%, HFD/HFR, Pulse, Dither, Autofokus) **für den sichtbaren Bereich**
- Links: Sitzungen (rot = Abbrüche/Settle-Fehler), Autofokus-Läufe → Klick springt zur Stelle
- Box-Zeit-Versatz: Box-Logs laufen ca. 1 h vor der App-Zeit (Standard −1 h, „Auto“ schätzt ihn aus den App-Logs)
- Export: CSV (sichtbarer Bereich), PNG, entschlüsselte Textdateien

---

## ⚖️ Rechtliche Hinweise & Haftungsausschluss

**Markenrechtlicher Hinweis** – Unabhängiges Open-Source-Werkzeug von der Community für die Community. Keine
geschäftliche, rechtliche oder organisatorische Verbindung zu ToupTek Astro oder deren Partnern. „ToupTek“ und
„StellaVita“ sind Marken der jeweiligen Eigentümer; die Namen dienen ausschließlich der Beschreibung der Kompatibilität.

**Haftungsausschluss (No Warranty)** – Die Software wird „wie besehen“ (as is) ohne ausdrückliche oder implizite
Garantie bereitgestellt. Der Entwickler übernimmt keine Haftung für Schäden an Hardware, Datenverlust oder entgangene
Astrofotografie-Sessions. Die Nutzung erfolgt vollständig auf eigene Gefahr.

**Datenschutz** – StellavitaLogsreader ist eine lokale Desktop-Anwendung. Logdateien werden ausschließlich auf Ihrem Rechner
verarbeitet; es werden keine Logdaten, GPS-Koordinaten oder persönlichen Informationen an einen Server übertragen
oder dort gespeichert.

## ⚖️ Legal notice & disclaimer

**Trademarks** – Independent open-source tool by the community, for the community. Not affiliated with, endorsed by
or connected to ToupTek Astro or its partners. "ToupTek" and "StellaVita" are trademarks of their respective owners;
the names are used solely to describe compatibility.

**No warranty** – The software is provided "as is", without warranty of any kind, express or implied. The author
accepts no liability for hardware damage, data loss or lost imaging sessions. Use at your own risk.

**Privacy** – StellavitaLogsreader is a local desktop application. Log files are processed on your computer only; no log data,
GPS coordinates or personal information is transmitted to or stored on any server.
