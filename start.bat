@echo off
rem Startet StellavitaLogsreader; fehlende Pakete (numpy, matplotlib) werden beim ersten Start automatisch nachinstalliert.
python stellavita_logsreader.py %*
if errorlevel 1 pause
