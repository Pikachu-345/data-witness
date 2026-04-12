@echo off
echo ============================================
echo   DataWitness v2.0 - Starting App
echo ============================================
echo.

echo [1/3] Installing Python packages...
pip install fastapi "uvicorn[standard]" python-multipart python-dotenv groq "httpx==0.27.0" pandas pyyaml python-dateutil pyvis --quiet

echo [2/3] Starting backend server (FastAPI on port 8000)...
start "DataWitness Backend" cmd /k "cd /d %~dp0 && uvicorn api.main:app --reload --port 8000"

echo.
echo Waiting 3 seconds for backend to start...
timeout /t 3 /nobreak > nul

echo [3/3] Starting frontend (React on port 5173)...
start "DataWitness Frontend" cmd /k "cd /d %~dp0frontend && npm install --silent && npm run dev"

echo.
echo ============================================
echo   Both servers are starting!
echo.
echo   Open your browser:  http://localhost:5173
echo ============================================
echo.
pause