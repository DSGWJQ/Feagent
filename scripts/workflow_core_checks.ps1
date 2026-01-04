$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Workflow Core Checks (local)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

if (-not (Test-Path ".import-linter.toml")) {
    Write-Host "错误: 请在仓库根目录运行该脚本（缺少 .import-linter.toml）" -ForegroundColor Red
    exit 1
}

Write-Host "[1/4] Import Linter (DDD boundaries)..." -ForegroundColor Green
if (-not (Get-Command lint-imports -ErrorAction SilentlyContinue)) {
    Write-Host "错误: 未找到 lint-imports，请先安装 dev 依赖（例如: uv pip install -e \".[dev]\"）" -ForegroundColor Red
    exit 1
}
lint-imports --config .import-linter.toml

Write-Host ""
Write-Host "[2/4] Fast DDD boundary checks..." -ForegroundColor Green
python scripts/ddd_boundary_checks.py

Write-Host ""
Write-Host "[3/4] Backend tests (targeted)..." -ForegroundColor Green
pytest -q `
    tests/unit/domain/services/test_workflow_save_validator.py `
    tests/integration/api/workflow_chat/test_chat_stream_react_api.py

Write-Host ""
Write-Host "[4/4] Frontend tests..." -ForegroundColor Green
Push-Location web
try {
    npm test
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "✅ All workflow core checks completed." -ForegroundColor Green
