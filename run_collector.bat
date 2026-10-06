@echo off
title HE THONG THU THAP DU LIEU VIDEO STREAMING - ALPR ITS 2026
echo ==============================================================================
echo   HE THONG THU THAP DU LIEU ANH STREAMING - ALPR ITS 2026
echo ==============================================================================
echo.
echo [*] Dang kiem tra thu vien Python can thiet...

python -c "import cv2, PIL, tkinter, yt_dlp" >nul 2>&1
if errorlevel 1 (
    echo [*] Phat hien thieu thu vien. Dang cai dat opencv-python Pillow yt-dlp...
    pip install opencv-python Pillow yt-dlp
    if errorlevel 1 (
        echo [!] Loi khi cai dat thu vien. Vui long kiem tra ket noi mang va thu lai.
        pause
        exit /b 1
    )
)

echo [*] Dang khoi dong giao dien thu thap: collector_gui.py ...
echo [*] Tan suat chup: 3.0s / 1 anh
echo [*] Tu dong phan chia folder theo tung gio (1h/folder): 00h-01h, 01h-02h...
echo.

python "%~dp0collector_gui.py"

if errorlevel 1 (
    echo.
    echo [!] Ung dung da dung lai voi ma loi.
    pause
)
