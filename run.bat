@echo off
title ResolvEd - Student Concern Routing & Resolution Tracking System
cd /d "%~dp0"

echo ======================================================================
echo    ResolvEd: Student Concern Routing and Resolution Tracking System
echo                   Midterm Practical Examination
echo ======================================================================
echo.

:: Detect Python executable
set PY_CMD=
where py >nul 2>&1 && set PY_CMD=py
if "%PY_CMD%"=="" where python >nul 2>&1 && set PY_CMD=python
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python39\python.exe"

if "%PY_CMD%"=="" (
    echo [ERROR] Python was not found on your system!
    echo Please ensure Python 3.9+ is installed.
    pause
    exit /b 1
)

echo [*] Python detected: %PY_CMD%
echo [*] Checking database...
if not exist "student_concerns.db" (
    echo [*] Initializing database and sample records...
    %PY_CMD% database.py
)

echo.
echo [*] Starting web server on http://127.0.0.1:5000 ...
echo [*] Opening your web browser automatically in 3 seconds...
echo.
echo ======================================================================
echo  DEMO ACCOUNTS FOR EVALUATION (Clickable on login page):
echo   - Admin:      demo.admin@email.com   / Admin@12345
echo   - Registrar:  staff.registrar@univ.edu / Staff@123
echo   - Finance:    staff.finance@univ.edu   / Staff@123
echo   - Student:    demo.user@email.com    / Student@12345
echo ======================================================================
echo.
echo [!] Keep this command window OPEN while using the system.
echo [!] To STOP the server, press Ctrl + C in this window.
echo.

:: Launch browser in background after 2 seconds
start "" cmd /c "timeout /t 2 >nul & start http://127.0.0.1:5000"

:: Start Flask app
%PY_CMD% app.py

pause
