@echo off
REM Deploy script - just run this!
REM Deploys d:\temp\lua.zip automatically with smart commit message

python deploy.py
if errorlevel 1 (
    echo Deploy failed!
    pause
    exit /b 1
)
pause
