@echo off
REM ── Supply Chain Alpha — Quick Start ──
REM Activates the virtual environment and launches the Streamlit UI.

cd /d "%~dp0"
call venv\Scripts\activate.bat
streamlit run app.py
