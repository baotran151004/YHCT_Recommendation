@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
npx -y concurrently --names "FastAPI,React" --prefix-colors "blue,green" "venv\Scripts\activate.bat && uvicorn main:app --reload" "cd yhct-frontend && npm start"
