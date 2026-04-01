@echo off
SETLOCAL

REM Set environment folder name
set ENV_NAME=venv

REM Check if virtual environment exists
IF NOT EXIST %ENV_NAME% (
    echo Creating virtual environment...
    python -m venv %ENV_NAME%
) ELSE (
    echo Virtual environment already exists.
)

REM Activate the virtual environment
echo Activating virtual environment...
call %ENV_NAME%\Scripts\activate

REM Upgrade pip (optional but recommended)
echo Upgrading pip...
python -m pip install --upgrade pip

REM Install requirements if file exists
IF EXIST requirements.txt (
    echo Installing dependencies...
    pip install -r requirements.txt
) ELSE (
    echo requirements.txt not found, skipping installation.
)

REM Run the main Python script
IF EXIST main.py (
    echo Running main.py...
    python main.py
) ELSE (
    echo main.py not found.
)

ENDLOCAL
pause