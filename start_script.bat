@echo off
echo Starting all services...

start "Client" cmd /k "cd client && npm run dev"

start "Server" cmd /k "cd server && .\venv\Scripts\activate.bat && uvicorn app.main:app --reload"

start "Rasa Actions" cmd /k "cd rasa && .\venv\Scripts\activate.bat && rasa run actions"

start "Rasa API" cmd /k "cd rasa && .\venv\Scripts\activate.bat && rasa run --enable-api --cors *"

start "AI Service" cmd /k "cd ai-service && .\venv\Scripts\activate.bat && uvicorn app.main:app --reload --port 8001"

echo All services started in individual terminals!