@echo off
where py >nul 2>nul
if not errorlevel 1 (
    py -3 "%~dp0open_2i.py" %*
) else (
    python "%~dp0open_2i.py" %*
)
if errorlevel 1 pause
