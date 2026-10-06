@echo off
title THU THAP ANH STREAM CHAT LUONG CAO BANG FFMPEG - ALPR ITS 2026
echo ==============================================================================
echo   BO TRICH XUAT ANH STREAM CHAT LUONG CAO VOI FFMPEG (CHONG MO NHOE)
echo ==============================================================================
echo.
echo [*] Kiem tra ffmpeg...
ffmpeg -version >nul 2>&1
if errorlevel 1 (
    echo [!] CHUA CO FFMPEG TRONG HE THONG!
    echo [!] Vui long cai dat ffmpeg: winget install Gyan.FFmpeg
    echo [!] Hoac tai ban portable tu: https://www.gyan.dev/ffmpeg/builds/
    pause
    exit /b 1
)

echo [*] Che do khuyen dung: 'sharpest' (Tu dong tim frame net nhat moi chu ky)
echo [*] Khac phuc 100%% hien tuong nho nhan khi chup xe chay (Motion Blur).
echo.

if "%~1"=="" (
    echo [!] Huong dan su dung dong lenh:
    echo     capture_ffmpeg.bat ^<URL_STREAM_HOAC_YOUTUBE^> [TAG] [INTERVAL] [FORMAT]
    echo.
    echo [?] Nhap URL Stream hoac link YouTube:
    set /p STREAM_URL="> "
) else (
    set STREAM_URL=%~1
)

if "%STREAM_URL%"=="" (
    echo [!] Khong co URL stream. Chuong trinh ket thuc.
    pause
    exit /b 1
)

set TAG=%~2
if "%TAG%"=="" set TAG=cam36

set INTERVAL=%~3
if "%INTERVAL%"=="" set INTERVAL=1.0

set FORMAT=%~4
if "%FORMAT%"=="" set FORMAT=jpg

echo.
echo [*] Bat dau thu thap tu: %STREAM_URL%
echo [*] Tag camera: %TAG%
echo [*] Chu ky: %INTERVAL%s / anh
echo [*] Dinh dang: %FORMAT% (Chat luong cao nhat)
echo.

python "%~dp0stream_capture_ffmpeg.py" --stream "%STREAM_URL%" --tag "%TAG%" --interval %INTERVAL% --mode sharpest --format %FORMAT% --quality 100

pause
