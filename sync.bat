@echo off

echo ===================================
echo OVERLEAF -> GITHUB SYNC
echo ===================================

git pull origin master

if errorlevel 1 (
    echo Napaka pri prenosu iz Overleafa.
    pause
    exit /b 1
)

git push github main

if errorlevel 1 (
    echo Napaka pri posiljanju na GitHub.
    pause
    exit /b 1
)

echo.
echo Sinhronizacija uspesna.
pause
