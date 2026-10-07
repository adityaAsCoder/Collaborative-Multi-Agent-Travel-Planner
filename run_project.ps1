$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonPath = Join-Path $projectRoot "venv\Scripts\python.exe"
$frontendPath = Join-Path $projectRoot "frontend"

if (-not (Test-Path $pythonPath)) {
    throw "Python virtual environment not found at $pythonPath. Create it and install requirements.txt first."
}

if (-not (Test-Path (Join-Path $frontendPath "node_modules"))) {
    throw "Frontend dependencies are missing. Run 'npm install' in the frontend directory first."
}

Start-Process `
    -FilePath $pythonPath `
    -ArgumentList "-m uvicorn app.api:app --reload --host 127.0.0.1 --port 8000" `
    -WorkingDirectory $projectRoot

Start-Process `
    -FilePath "npm.cmd" `
    -ArgumentList "run dev -- --host 127.0.0.1" `
    -WorkingDirectory $frontendPath

Write-Host "WanderWise is starting."
Write-Host "Backend API: http://127.0.0.1:8000"
Write-Host "API docs:    http://127.0.0.1:8000/docs"
Write-Host "Frontend:    http://127.0.0.1:5173"
