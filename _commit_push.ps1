# _commit_push.ps1
# 单次提交并推送(从 webapp 目录运行)
# 用法:.\\_commit_push.ps1
param(
    [string]$Message = "manual update"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> git add -A" -ForegroundColor Cyan
git add -A

$staged = git diff --cached --name-only
if (-not $staged) {
    Write-Host "==> 无 staged 改动,跳过" -ForegroundColor Yellow
    exit 0
}
Write-Host "==> staged files:" -ForegroundColor Gray
$staged | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }

Write-Host "==> git commit -m $Message" -ForegroundColor Cyan
git commit -m $Message 2>&1 | Out-String | Write-Host

Write-Host "==> git push" -ForegroundColor Cyan
git push 2>&1 | Out-String | Write-Host

if ($LASTEXITCODE -eq 0) {
    Write-Host "==> 完成" -ForegroundColor Green
} else {
    Write-Host "==> 失败" -ForegroundColor Red
    exit 1
}
