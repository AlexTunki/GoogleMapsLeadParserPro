@echo off
chcp 65001 > nul
cd /d "%~dp0"

python -c "import playwright; import fastapi; import uvicorn" >nul 2>&1
if %errorlevel% neq 0 (
    echo ==============================================
    echo Первоначальная настройка парсера Google Maps...
    echo ==============================================
    echo.
    echo 1. Установка библиотек...
    pip install -r requirements.txt
    
    echo.
    echo 2. Загрузка скрытого браузера Chromium...
    playwright install chromium
    if %errorlevel% neq 0 (
        echo ОШИБКА: Не удалось установить Chromium.
        pause
        exit /b %errorlevel%
    )
    echo Установка успешно завершена!
    echo.
)

echo ==============================================
echo Запускаем быстрый парсер Google Maps...
echo ВНИМАНИЕ: Сейчас откроется веб-браузер с программой!
echo ==============================================
python app.py

echo.
echo Скрипт завершил работу.
pause