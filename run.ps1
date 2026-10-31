# Start the backend on :$env:PORT (default 8000). Frontend: cd frontend; npm run dev
$port = if ($env:PORT) { $env:PORT } else { "8000" }
Set-Location "$PSScriptRoot\backend"
& ..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port $port
