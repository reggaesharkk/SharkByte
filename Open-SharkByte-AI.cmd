@echo off
powershell.exe -NoProfile -File "%~dp0Open-SharkByte-AI.ps1"
if errorlevel 1 pause
