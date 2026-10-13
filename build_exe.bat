@echo off
rem StellavitaLogsreader als einzelne EXE bauen (Windows, Python 3.9+)
python -m pip install --upgrade pip numpy matplotlib pyinstaller
python -m PyInstaller --onefile --windowed --name StellavitaLogsreader --hidden-import matplotlib.backends.backend_tkagg stellavita_logsreader.py
echo.
echo Fertig: dist\StellavitaLogsreader.exe
pause
