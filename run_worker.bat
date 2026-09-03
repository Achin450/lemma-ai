@echo off
echo =======================================================================
echo                 STARTING CELERY WORKER
echo =======================================================================
echo.

cd /d "%~dp0"

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Set PYTHONPATH so python can find the 'app' module
set PYTHONPATH=backend

:: Start celery worker in solo mode
celery -A app.tasks.celery_app.celery_app worker --loglevel=info -P solo

pause
