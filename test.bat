@echo off
title ResolvEd - Automated Midterm Test Suite
cd /d "%~dp0"

echo ======================================================================
echo    ResolvEd: Automated Test Suite (10 Examination Test Cases)
echo ======================================================================
echo.

set PY_CMD=
if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
if "%PY_CMD%"=="" where py >nul 2>&1 && set PY_CMD=py
if "%PY_CMD%"=="" where python >nul 2>&1 && set PY_CMD=python

echo [*] Running all 10 examination test cases...
echo.

%PY_CMD% -m unittest tests/test_system.py

echo.
echo ======================================================================
echo  Test run complete. All tests should display OK above.
echo ======================================================================
pause
