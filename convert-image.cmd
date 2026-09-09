@echo off
:: ============================================
:: Image Format Converter
:: Version: 1.1.0
:: Author: Usef Farahmand
:: GitHub: https://github.com/Usef-Farahmand
:: ============================================
setlocal enabledelayedexpansion

set "scriptdir=%~dp0"
set "appversion=1.1.0"

:menu
echo ============================================
echo    Image Format Converter (No Software Needed)
echo    v%appversion%
echo ============================================
echo.

:: Get the source image path from the user
set /p "srcfile=Enter the image file path (or drag and drop the file here): "

:: Strip surrounding quotes if the file was dragged in
set "srcfile=%srcfile:"=%"

if not exist "%srcfile%" (
    echo Error: No file found at that path.
    echo.
    goto ask_continue
)

:: Get the target format from the user (menu selection instead of free typing)
echo.
echo Select the target format:
echo   [1] jpg
echo   [2] png
echo   [3] bmp
echo   [4] gif
echo   [5] tiff
echo   [6] ico
echo.
echo (Note: svg is NOT supported - it is a vector format and requires a dedicated tool such as Inkscape)
echo.
choice /c 123456 /n /m "Enter your choice (1-6): "

if errorlevel 6 set "targetfmt=ico"
if errorlevel 5 if not errorlevel 6 set "targetfmt=tiff"
if errorlevel 4 if not errorlevel 5 set "targetfmt=gif"
if errorlevel 3 if not errorlevel 4 set "targetfmt=bmp"
if errorlevel 2 if not errorlevel 3 set "targetfmt=png"
if errorlevel 1 if not errorlevel 2 set "targetfmt=jpg"

:: Extract the folder and filename without extension
for %%F in ("%srcfile%") do (
    set "dir=%%~dpF"
    set "name=%%~nF"
)

set "outfile=!dir!!name!.%targetfmt%"

echo.
echo Converting...

powershell -NoProfile -ExecutionPolicy Bypass -File "%scriptdir%convert-image.ps1" -SourcePath "%srcfile%" -TargetFormat "%targetfmt%" -OutputPath "%outfile%"

if errorlevel 1 (
    echo.
    echo Conversion failed. Please check the format you entered.
) else (
    echo.
    echo Conversion completed successfully.
    echo Output file: !outfile!
    echo.
    echo Opening output folder...
    explorer /select,"!outfile!"
)

:ask_continue
echo.
choice /c CX /n /m "Press [C] to convert another image, or [X] to exit: "

if errorlevel 2 goto end
if errorlevel 1 (
    echo.
    cls
    goto menu
)

:end
echo.
echo Goodbye!
exit /b 0
