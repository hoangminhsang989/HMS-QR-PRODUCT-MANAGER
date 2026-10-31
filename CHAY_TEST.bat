@echo off
chcp 65001 >nul
setlocal
title HMS QR Test Suite
REM Run the whole test suite.
REM
REM The test root used to live on F:, which was silently corrupting
REM directories while pytest wrote to them: the run that reported 447 errors
REM left its basetemp unreadable, and runs after it failed in different places
REM each time. chkdsk F: /f is the real fix but it needs the machine owner.
REM
REM H: used to hold the test root; that drive no longer exists on this
REM machine, so the root now lives at D:\HMS-QR-CHECK. The move is safe only
REM because the reference fixture travels with the root: the Excel fidelity
REM gate reads <root>\reference\excel-template.xlsx and silently SKIPS when it
REM is missing, which would hide a check instead of failing it. The customer
REM workbook is an external input and is not in this repo - copy it whenever
REM the root is recreated.
REM
REM Do not point HMS_QR_TEST_ROOT at the repository. config.paths rejects it
REM outright (must remain outside the source package).

set "HMS_QR_TEST_ROOT=D:\HMS-QR-CHECK"
set "HMS_QR_EXCEL_REFERENCE_TEMPLATE=%HMS_QR_TEST_ROOT%\reference\excel-template.xlsx"
set "PYTHONPATH=%~dp0."
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONIOENCODING=utf-8"

if not exist "%HMS_QR_TEST_ROOT%" mkdir "%HMS_QR_TEST_ROOT%"
if not exist "%HMS_QR_TEST_ROOT%\reference" mkdir "%HMS_QR_TEST_ROOT%\reference"

if not exist "%HMS_QR_EXCEL_REFERENCE_TEMPLATE%" (
  echo [WARN] Reference Excel template is missing:
  echo        %HMS_QR_EXCEL_REFERENCE_TEMPLATE%
  echo.
  echo        tests\stage6\test_template_fidelity_reference.py will SKIP, so the
  echo        suite stays green without proving fidelity. Copy the customer
  echo        workbook there to re-enable that gate.
  echo.
)

REM A fresh basetemp per run: an old one can be left unreadable by a crash, and
REM sharing one between runs makes a dead lock file look like a test failure.
REM %DATE% is locale-dependent (it contains separators on this machine), so
REM parsing it would put slashes in the path and create nested directories.
REM Two randoms are enough - a collision only means reusing a stale basetemp,
REM which the next line already guards against.
set "BNAME=pytest-temp-%RANDOM%%RANDOM%"
set "BTEMP=%HMS_QR_TEST_ROOT%\%BNAME%"
if exist "%BTEMP%" (
  echo [FAIL] Basetemp %BTEMP% already exists; rerun for a fresh name.
  exit /b 1
)

if "%~1"=="" (
  py -3.14 -m pytest tests -q --no-header --basetemp="%BTEMP%" -p no:cacheprovider
) else (
  py -3.14 -m pytest %* --basetemp="%BTEMP%" -p no:cacheprovider
)
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [FAIL] Suite finished with exit code %RC%. Basetemp kept for inspection:
  echo        %BTEMP%
  exit /b %RC%
)

echo.
echo [OK] Suite passed. Basetemp: %BTEMP%
exit /b 0
