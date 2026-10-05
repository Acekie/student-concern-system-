@echo off
title ResolvEd - Automated Midterm Test Suite
cd /d "%~dp0"

echo ======================================================================
echo    ResolvEd: Automated Test Suite (10 Examination Test Cases)
echo ======================================================================
echo.

set PY_CMD=
where py >nul 2>&1 && set PY_CMD=py
if "%PY_CMD%"=="" where python >nul 2>&1 && set PY_CMD=python
if "%PY_CMD%"=="" if exist "%LOCALAPPDATA%\Programs\Python\Python39\python.exe" set PY_CMD="%LOCALAPPDATA%\Programs\Python\Python39\python.exe"

echo [*] Running test cases:
echo     TC01: Valid Login
echo     TC02: Invalid Login
echo     TC03: Concern Submission
echo     TC04: Business Rule 1 (Auto Department Routing)
echo     TC05: Business Rule 2 (SLA Target Calculation)
echo     TC06: Status Workflow Processing
echo     TC07: Business Rule 3 (Mandatory Resolution Notes)
echo     TC08: Student Resolution Feedback and Closure
echo     TC09: Search and Multi-Attribute Filtering
echo     TC10: Production Persistence
echo.

%PY_CMD% -m unittest tests/test_system.py

echo.
echo ======================================================================
echo  Test run complete. All tests should display OK above.
echo ======================================================================
pause
