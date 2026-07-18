@echo off
chcp 65001 >nul

echo (c) 2026 ReviveMii, TheErrorExe. All Rights Reserved
echo.
echo ========================================
echo   RiiviveTube Custom Instance Setup
echo ========================================
echo.

set /p SERVER_ADDR="Enter your custom server address (e.g. 192.168.1.100 or 192.168.1.100:5005, run 'ip a' to get your local IP. 5005 is the default port of RiiviveTube): "

if "%SERVER_ADDR%"=="" (
    echo Error: No address provided. Exiting.
    exit /b 1
)

echo.
echo Replacing ReviveMii Adress with '%SERVER_ADDR%'...

set "FILES=main.py youtubei.py assets\leanback_ajax.json"

for %%f in (%FILES%) do (
    if exist "%%f" (
        powershell -Command "(Get-Content '%%f') -replace 'ytv2.nossl.revivemii.xyz', '%SERVER_ADDR%' | Set-Content '%%f'"
        echo   Patched: %%f
    ) else (
        echo   Warning: %%f not found, skipping.
    )
)

echo.
echo Downloading ReplaceInSwf...

set "JAR_URL=https://github.com/ReviveMii/ReplaceInSwf/releases/download/v1.0.0/replace-in-swf-1.0.0.jar"
set "JAR_FILE=replace-in-swf-1.0.0.jar"

if not exist "%JAR_FILE%" (
    powershell -Command "Invoke-WebRequest -Uri '%JAR_URL%' -OutFile '%JAR_FILE%'"
    echo   Downloaded: %JAR_FILE%
) else (
    echo   %JAR_FILE% already exists, skipping download.
)

echo.
echo Patching .swf files...

if exist "assets" (
    for %%s in (assets\*.swf) do (
        echo   Patching: %%~nxs
        java -jar "%JAR_FILE%" "%%s" "%%s" "ytv2.nossl.revivemii.xyz" "%SERVER_ADDR%" >nul 2>&1
    )
) else (
    echo   Warning: assets\ directory not found.
)

echo.
echo ========================================
echo   Done! Your instance is configured.
echo   Server: %SERVER_ADDR%
echo   Run 'main.py' to start it
echo ========================================

pause
