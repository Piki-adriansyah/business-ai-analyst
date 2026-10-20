@echo off
setlocal
cd /d "%~dp0"
title Business AI Analyst - Windows

echo ==========================================
echo         BUSINESS AI ANALYST
echo ==========================================
echo.
if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Membuat virtual environment...
  py -3 -m venv .venv
  if errorlevel 1 (
    echo ERROR: Python tidak ditemukan. Instal Python dan centang Add Python to PATH.
    pause
    exit /b 1
  )
)

if not exist ".venv\.installed_ok" (
  echo [2/3] Menginstal dependensi (butuh internet untuk pertama kali)...
  ".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements.txt
  if errorlevel 1 (
    echo Gagal menginstal paket. Periksa koneksi internet.
    pause
    exit /b 1
  )
  echo ok>".venv\.installed_ok"
)

echo [3/3] Menjalankan app di http://localhost:8501
".venv\Scripts\python.exe" -m streamlit run app.py
pause
