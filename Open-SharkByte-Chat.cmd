@echo off
cd /d "%~dp0"
python -B sharkbyte_chat.py %*
if errorlevel 1 pause
