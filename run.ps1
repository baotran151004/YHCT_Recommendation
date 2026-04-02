$env:PYTHONIOENCODING="utf-8"
$OutputEncoding = [Console]::InputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding
npx -y concurrently --names "FastAPI,React" --prefix-colors "blue,green" "venv\Scripts\activate.bat && uvicorn main:app --reload" "cd yhct-frontend && npm start"
