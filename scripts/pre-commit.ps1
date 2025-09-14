# PowerShell pre-commit script for Windows
# Run this before committing to catch issues locally

Write-Host "🚀 Running pre-commit checks..." -ForegroundColor Green

# Change to project root
Set-Location (Split-Path $PSScriptRoot)

# Run the automated checks
python scripts/check-code.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n💡 Tip: Run 'python scripts/fix-code.py' to automatically fix common issues" -ForegroundColor Yellow
    exit $LASTEXITCODE
}