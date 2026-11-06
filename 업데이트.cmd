@echo off
rem Bring the newest release of the distribution into this office (Windows).
rem   (double-click)     show what comes in and ask before merging
rem   with --check       only show; changes nothing
rem   with /y or --yes   merge without asking (after you have seen --check)
rem Claude runs the Python tool itself: --check first, your approval, then --yes.
rem The work is done by the Python tool with this file's name in the tools folder; this file only finds
rem Python 3.8 or later. The tool is looked up by name so this file holds no Korean text: cmd reads batch
rem files in the console code page. It never pushes: run the sync file afterwards to upload.
setlocal

rem cmd reads a batch file from disk line by line while it runs, and receiving a new release may rewrite
rem this very file. So run a copy from the temp folder (the whole block below is read before it runs).
if not defined LEGAL_OFFICE_DIR (
  set "LEGAL_OFFICE_DIR=%~dp0"
  if not exist "%TEMP%\legal-office-run\" mkdir "%TEMP%\legal-office-run" >nul 2>&1
  copy /y "%~f0" "%TEMP%\legal-office-run\%~nx0" >nul 2>&1
  if errorlevel 1 goto inplace
  call "%TEMP%\legal-office-run\%~nx0" %*
  exit /b
)
goto start
:inplace
set "LEGAL_OFFICE_DIR=%~dp0"
:start
cd /d "%LEGAL_OFFICE_DIR%"

rem Arguments: /y means --yes, anywhere on the line; everything else is passed on as it is.
set "ARGS="
set "YES="
:args
if "%~1"=="" goto argsdone
if /i "%~1"=="/y" (set "ARGS=%ARGS% --yes" & set "YES=1") else (set "ARGS=%ARGS% %1")
if /i "%~1"=="--yes" set "YES=1"
shift
goto args
:argsdone

set "TOOL="
for /d %%d in ("%LEGAL_OFFICE_DIR%*") do if exist "%%~fd\%~n0.py" set "TOOL=%%~fd\%~n0.py"
if not defined TOOL goto notool

set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY goto nopython

%PY% "%TOOL%" %ARGS%
set "RC=%errorlevel%"
if not defined YES pause
exit /b %RC%

:notool
echo.
echo Update stopped: the update tool was not found in the tools folder. Nothing was changed.
goto stop

:nopython
echo.
echo Update stopped: Python 3.8 or later was not found (py -3 or python). Nothing was changed.

:stop
if not defined YES pause
exit /b 1
