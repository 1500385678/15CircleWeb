@echo off
REM _commit_push.bat - Windows 批处理版
REM 用法: _commit_push.bat "commit message"

setlocal
cd /d "%~dp0"

if "%~1"=="" set "MSG=manual update" else set "MSG=%~1"

echo ==> git add -A
git add -A

git diff --cached --name-only > "%TEMP%\staged.txt"
for /f %%i in ("%TEMP%\staged.txt") do set "LINES=%%i"
del "%TEMP%\staged.txt"

if "%LINES%"=="" (
    echo ==> 无 staged 改动,跳过
    exit /b 0
)

echo ==> git commit -m "%MSG%"
git commit -m "%MSG%"

echo ==> git push
git push

if %ERRORLEVEL%==0 (echo ==> 完成) else (echo ==> 失败 & exit /b 1)
