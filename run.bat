@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
npx -y concurrently --names "FastAPI,React" --prefix-colors "blue,green" "venv\Scripts\activate.bat && cd backend && uvicorn main:app --reload" "cd frontend && npm start"
