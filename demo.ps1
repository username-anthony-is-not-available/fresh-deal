# Native PowerShell Demo Setup for Local Windows Execution
Write-Host "🍽️  Smart Meal Planner Local Demo" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan

$root = $PSScriptRoot
$backendDir = "$root\smart-meal-planner\backend"
$frontendDir = "$root\smart-meal-planner\frontend"

if (-not (Test-Path $backendDir)) {
    if (Test-Path "$root\backend") {
        $backendDir = "$root\backend"
        $frontendDir = "$root\frontend"
    } else {
        Write-Error "Backend directory not found!"
        exit 1
    }
}

$envFile = "$backendDir\.env"
$envDevFile = "$backendDir\.env.development"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envDevFile) {
        Copy-Item $envDevFile $envFile
        Write-Host "✅ Copied .env.development to .env" -ForegroundColor Green
    } else {
        @"
OPENROUTER_API_KEY=dummy_key_for_local_mock
USE_SQLITE_LOCAL=True
USE_MOCK_AI=True
ENVIRONMENT=development
"@ | Out-File -FilePath $envFile -Encoding utf8
        Write-Host "✅ Created $envFile template" -ForegroundColor Green
    }
}

# Set environment variables for local execution
$env:USE_SQLITE_LOCAL = "True"
$env:USE_MOCK_AI = "True"
$env:ENVIRONMENT = "development"

Write-Host "🚀 Starting Backend (FastAPI on http://localhost:8000)..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($dir, $venvPython)
    Set-Location $dir
    $env:USE_SQLITE_LOCAL = "True"
    $env:USE_MOCK_AI = "True"
    if (Test-Path "$dir\..\..\.venv\Scripts\uvicorn.exe") {
        & "$dir\..\..\.venv\Scripts\uvicorn.exe" app.main:app --reload --port 8000
    } else {
        uvicorn app.main:app --reload --port 8000
    }
} -ArgumentList $backendDir

Start-Sleep -Seconds 3

Write-Host "🎨 Starting Frontend (Vite on http://localhost:5173)..." -ForegroundColor Yellow
$frontendJob = Start-Job -ScriptBlock {
    param($dir)
    Set-Location $dir
    npm run dev
} -ArgumentList $frontendDir

Write-Host "`n✅ Local services started!" -ForegroundColor Green
Write-Host "   Frontend: http://localhost:5173" -ForegroundColor White
Write-Host "   Backend:  http://localhost:8000" -ForegroundColor White
Write-Host "   API Docs: http://localhost:8000/docs" -ForegroundColor White
Write-Host "`nPress Ctrl+C to stop all services..." -ForegroundColor Cyan

try {
    while ($true) {
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`n🛑 Stopping local services..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -ErrorAction SilentlyContinue
    Stop-Job $frontendJob -ErrorAction SilentlyContinue
    Remove-Job $frontendJob -ErrorAction SilentlyContinue
    Write-Host "✅ All services stopped." -ForegroundColor Green
}
