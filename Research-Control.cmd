@echo off
cd /d "%~dp0"
start "Stack Ledger research control" /min python scripts\research_control.py --open
