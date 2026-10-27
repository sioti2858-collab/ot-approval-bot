@echo off
title OT Bot - Stats Monitor
cd /d %~dp0
python monitor.py --stats
pause