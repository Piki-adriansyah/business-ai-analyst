@echo off
setlocal
cd /d "%~dp0"
title Business AI Analyst V2 - Windows

echo =========================================
echo       BUSINESS AI ANALYST V2
echo =========================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo Membuat virtual environment Python...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERROR: Python belum tersedia. Silakan instal Python terlebih dahulu.
    pause
    exit /b 1
  )
)
echo Memeriksa dan memasang dependency V2...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
  echo Gagal menginstal dependency. Periksa internet dan ruang disk.
  pause
  exit /b 1
)
echo Menjalankan http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
pause
