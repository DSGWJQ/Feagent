@echo off
cd /d %~dp0\..
python -m uvicorn src.interfaces.api.main:app --port 8000
pause

