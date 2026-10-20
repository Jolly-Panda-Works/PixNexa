@echo off
cd /d "%~dp0"
python -m venv .venv-build
call .venv-build\Scripts\activate
pip install -r requirements.txt pyinstaller
for /f %%v in ('python tools\set_version.py') do set VER=%%v
echo Building PixNexa Desktop %VER%
pyinstaller --noconfirm --onedir --windowed --name PixNexa --icon assets/icon.ico --version-file version_info.txt --add-data "assets;assets" --collect-all customtkinter --collect-all tkinterdnd2 --collect-submodules pixnexa_engines --hidden-import self_test --collect-all pi_heif --collect-all pypdfium2 --collect-all pypdfium2_raw --collect-all pikepdf --collect-all py7zr --collect-submodules fontTools --collect-submodules markdown --collect-submodules pysubs2 --collect-submodules openpyxl --hidden-import brotli --hidden-import yaml --hidden-import tomli_w image_converter_gui.py
if errorlevel 1 goto :failed
rem FFmpeg (video, audio and HEIC output) is downloaded once, checksum-verified, and placed next to the exe.
powershell -NoProfile -ExecutionPolicy Bypass -File tools\fetch_ffmpeg.ps1 -Dest dist\PixNexa\ffmpeg
if errorlevel 1 echo WARNING: FFmpeg could not be downloaded. Video and audio will not work in this build.
copy /y LICENSE dist\PixNexa\ >nul
copy /y THIRD-PARTY-NOTICES.md dist\PixNexa\ >nul
dist\PixNexa\PixNexa.exe --self-test
if errorlevel 1 echo WARNING: the self-test failed, see %TEMP%\PixNexa-self-test.txt
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=%VER% installer.iss
del _build_version.py version_info.txt 2>nul
echo.
echo Done: dist\PixNexa\PixNexa.exe  (version %VER%)
if exist Output\PixNexa_Setup.exe echo Installer: Output\PixNexa_Setup.exe
pause
exit /b 0

:failed
echo PyInstaller failed.
del _build_version.py version_info.txt 2>nul
pause
exit /b 1
