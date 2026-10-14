@echo off
cd /d "%~dp0"
python -m venv .venv-build
call .venv-build\Scripts\activate
pip install -r requirements.txt pyinstaller
for /f %%v in ('python tools\set_version.py') do set VER=%%v
echo Building Image Format Converter %VER%
pyinstaller --noconfirm --onedir --windowed --name ImageFormatConverter --icon assets/icon.ico --version-file version_info.txt --add-data "assets;assets" --collect-all customtkinter --collect-all tkinterdnd2 image_converter_gui.py
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=%VER% installer.iss
del _build_version.py version_info.txt 2>nul
echo.
echo Done: dist\ImageFormatConverter\ImageFormatConverter.exe  (version %VER%)
if exist Output\ImageFormatConverter_Setup.exe echo Installer: Output\ImageFormatConverter_Setup.exe
pause
