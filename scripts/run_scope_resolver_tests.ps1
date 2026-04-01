# Phase 2 verification: start disposable Postgres (Docker), run pytest + runtime proof.
# Requires Docker Desktop / docker on PATH.
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$testUrl = "postgresql+psycopg2://vcfo:vcfo@127.0.0.1:5433/vcfo_test"
$env:TEST_DATABASE_URL = $testUrl

$docker = Get-Command docker -ErrorAction SilentlyContinue
if (-not $docker) {
    Write-Host "docker not found on PATH. Install Docker Desktop or set TEST_DATABASE_URL to a working PostgreSQL URL, then run:" -ForegroundColor Yellow
    Write-Host "  python -m pytest tests/test_scope_resolver.py -v" -ForegroundColor Yellow
    Write-Host "  python scripts/prove_scope_resolver.py" -ForegroundColor Yellow
    exit 2
}

docker compose -f docker-compose.test.yml up -d
$deadline = (Get-Date).AddSeconds(60)
do {
    try {
        docker exec vcfo-postgres-test pg_isready -U vcfo -d vcfo_test 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
    } catch { }
    Start-Sleep -Seconds 2
    if ((Get-Date) -gt $deadline) {
        Write-Host "Timeout waiting for PostgreSQL health." -ForegroundColor Red
        exit 3
    }
} while ($true)

python -m pytest tests/test_scope_resolver.py -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python scripts/prove_scope_resolver.py
exit $LASTEXITCODE
