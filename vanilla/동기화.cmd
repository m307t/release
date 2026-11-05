@echo off
rem Sync this folder with the private GitHub repository (Windows).
rem   (double-click)     show the changes and ask before uploading
rem   with /y or --yes   upload without asking. Claude does not use this file: after showing you
rem                      the list it runs the .sh script in this folder with --yes (Git Bash).
rem Order: commit local changes, pull others' changes on top, check for conflict markers, push.
rem A real conflict stops the script before anything is uploaded.
setlocal
cd /d "%~dp0"
set "YES="
if /i "%~1"=="/y" set "YES=1"
if /i "%~1"=="--yes" set "YES=1"

rem Run only at the top of this folder's own git repository. When this folder sits inside another
rem repository (for example vanilla inside the distribution repository), git would commit and push
rem that outer repository instead, so stop before touching anything.
set "TOP="
for /f "delims=" %%t in ('git rev-parse --show-toplevel 2^>nul') do set "TOP=%%t"
if not defined TOP goto nottop
set "TOP=%TOP:/=\%"
if /i "%TOP%"=="%CD%" goto toplevel
rem Non-ASCII folder names can differ here only by console code page, so ask git for the prefix too.
set "PREFIX="
for /f "delims=" %%p in ('git rev-parse --show-prefix 2^>nul') do set "PREFIX=%%p"
if defined PREFIX goto nottop
:toplevel

rem 0. Do not start on top of an unfinished merge or rebase (same test as the .sh script).
git rev-parse -q --verify MERGE_HEAD >nul 2>&1
if not errorlevel 1 goto unfinished
call :rebasing
if defined REBASING goto unfinished

rem 1. Commit local changes first, after showing every file (new folders are listed file by file).
set "CHANGED="
for /f "delims=" %%l in ('git status --porcelain') do set "CHANGED=1"
if not defined CHANGED goto pull
echo Changes to upload:
git -c core.quotepath=false status --short --untracked-files=all
if defined YES goto commit
set "ANS="
set /p ANS="Upload these changes? [y/N] "
if /i "%ANS%"=="y" goto commit
if /i "%ANS%"=="yes" goto commit
echo.
echo Sync cancelled. Nothing was uploaded or downloaded.
pause
exit /b 0

:commit
git add -A
if errorlevel 1 goto fail
git commit -q -m "sync: %COMPUTERNAME% %DATE% %TIME%"
if errorlevel 1 goto fail

:pull
rem 2. Pull others' changes on top. On a real conflict, undo the pull and stop.
git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >nul 2>&1
if errorlevel 1 goto check
git pull --rebase -q
if not errorlevel 1 goto check
call :rebasing
if defined REBASING goto conflict
echo.
echo Sync stopped: pull failed. Check the network, GitHub sign-in and the remote branch.
echo Nothing was uploaded.
goto help

:check
rem 3. Never upload conflict markers.
git grep -I -q -E "^(<<<<<<<|>>>>>>>)( |$)" -- .
if not errorlevel 1 goto markers

rem 4. Upload. Commits that were already made are listed first. A new branch gets its upstream here.
git rev-parse --abbrev-ref --symbolic-full-name "@{u}" >nul 2>&1
if errorlevel 1 goto pushnew
echo Commits to upload:
git -c core.quotepath=false log --oneline "@{u}..HEAD"
git push -q
if errorlevel 1 goto fail
goto done
:pushnew
git push -q -u origin HEAD
if errorlevel 1 goto fail

:done
echo.
echo Sync done.
for /f "delims=" %%b in ('git rev-parse --abbrev-ref HEAD') do if /i not "%%b"=="main" echo Note: this branch (%%b) is not main. Merge it into main so other PCs receive it.
if not defined YES pause
exit /b 0

:rebasing
rem Sets REBASING when a rebase is really in progress. A leftover REBASE_HEAD file alone does not count.
set "REBASING="
for /f "delims=" %%d in ('git rev-parse --git-path rebase-merge') do if exist "%%~fd\" set "REBASING=1"
for /f "delims=" %%d in ('git rev-parse --git-path rebase-apply') do if exist "%%~fd\" set "REBASING=1"
exit /b 0

:conflict
git rebase --abort >nul 2>&1
echo.
echo Sync stopped: your changes conflict with another PC.
echo Nothing was uploaded. Your changes are kept on this PC as a local commit.
goto conflicthelp

:markers
git -c core.quotepath=false grep -I -n -E "^(<<<<<<<|>>>>>>>)( |$)" -- .
echo.
echo Sync stopped: conflict markers were found. Nothing was uploaded.
goto conflicthelp

:nottop
echo.
echo Sync stopped: this folder is not the top of its own git repository.
echo For example it is vanilla inside the distribution repository, or a folder without git.
echo Nothing was uploaded or downloaded. Copy this folder out, make it your own repository
echo first as in README, first PC, step 3, and run this file there.
goto stop

:unfinished
echo.
echo Sync stopped: an earlier merge or rebase is unfinished.
goto help

:fail
echo.
echo Sync failed. Read the messages above.

:help
echo Show the messages above to Claude, or ask Claude to resolve the sync.
goto stop

:conflicthelp
echo Ask Claude to resolve the sync conflict.

:stop
if not defined YES pause
exit /b 1
