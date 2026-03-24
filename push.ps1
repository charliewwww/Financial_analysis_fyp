# push.ps1 — Commit all changes and push to both GitLab (origin) and GitHub
# Usage:
#   .\push.ps1                        # auto-generates commit message from changed files
#   .\push.ps1 "your commit message"  # custom commit message

param(
    [string]$Message = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ── Stage all changes ────────────────────────────────────────────
git add -A

# ── Check if there's anything to commit ──────────────────────────
$status = git status --porcelain
if (-not $status) {
    Write-Host "Nothing to commit — working tree clean." -ForegroundColor Yellow
    exit 0
}

# ── Build commit message ─────────────────────────────────────────
if (-not $Message) {
    $changed = git diff --cached --name-only | Select-Object -First 5
    $fileList = ($changed -join ", ")
    $Message = "update: $fileList"
}

# ── Commit ───────────────────────────────────────────────────────
git commit -m $Message
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# ── Push to GitLab (origin) ───────────────────────────────────────
Write-Host "`nPushing to GitLab (origin)..." -ForegroundColor Cyan
git push origin HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitLab push failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

# ── Push to GitHub ────────────────────────────────────────────────
Write-Host "`nPushing to GitHub..." -ForegroundColor Cyan
git push github HEAD
if ($LASTEXITCODE -ne 0) {
    Write-Host "GitHub push failed." -ForegroundColor Red
    exit $LASTEXITCODE
}

Write-Host "`nDone — pushed to both GitLab and GitHub." -ForegroundColor Green
