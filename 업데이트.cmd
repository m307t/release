@echo off
rem Bring the newest release of the distribution into this office (Windows).
rem   (double-click)     show what comes in and ask before merging
rem   with --check       only show; changes nothing
rem   with /y or --yes   merge without asking (Claude runs the .sh script with --yes instead)
rem The work is done by the Python tool with this file's name in the tools folder; this file only finds
rem Python 3.8 or later. The tool is looked up by name so this file holds no Korean text: cmd reads batch
rem files in the console code page. It never pushes: run the sync file afterwards to upload.
setlocal
cd /d "%~dp0"
set "ARGS=%*"
set "YES="
if /i "%~1"=="/y" (set "ARGS=--yes" & set "YES=1")
if /i "%~1"=="--yes" set "YES=1"

set "TOOL="
for /d %%d in ("%~dp0*") do if exist "%%~fd\%~n0.py" set "TOOL=%%~fd\%~n0.py"
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
