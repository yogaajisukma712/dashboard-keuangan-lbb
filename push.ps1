# GitHub Push Script for Dashboard Keuangan LBB Super Smart
# This script will push your Flask project to GitHub

$GITHUB_USERNAME = "hnoivvs"
$GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"  # Replace with your token
$GITHUB_REPO = "lbb-super-smart"
$GITHUB_EMAIL = "admin@lbb-super-smart.com"
$PROJECT_PATH = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "GitHub Push Script" -ForegroundColor Cyan
Write-Host "Dashboard Keuangan LBB Super Smart" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Project path: $PROJECT_PATH" -ForegroundColor Yellow
Write-Host "GitHub username: $GITHUB_USERNAME" -ForegroundColor Yellow
Write-Host "Repository: $GITHUB_REPO" -ForegroundColor Yellow

# Step 1: Configure git
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STEP 1: Configure Git" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Push-Location $PROJECT_PATH
git config user.name "LBB Super Smart"
git config user.email $GITHUB_EMAIL

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to configure git" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Git configured" -ForegroundColor Green

# Step 2: Initialize repository
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STEP 2: Initialize Repository" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if (Test-Path ".git") {
    Write-Host "⚠️  Repository already initialized, skipping init" -ForegroundColor Yellow
} else {
    git init
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Failed to initialize git repository" -ForegroundColor Red
        exit 1
    }
    Write-Host "✅ Git repository initialized" -ForegroundColor Green
}

# Step 3: Add all files
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STEP 3: Add All Files" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

git add .
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to add files" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Files added" -ForegroundColor Green

# Step 4: Create commit
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STEP 4: Create Commit" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

git commit -m "Initial commit: Dashboard Keuangan LBB Super Smart - Ready for Railway deployment"
if ($LASTEXITCODE -ne 0) {
    Write-Host "⚠️  Commit might have failed or no changes to commit" -ForegroundColor Yellow
}
Write-Host "✅ Commit created" -ForegroundColor Green

# Step 5: Add remote
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STEP 5: Add Remote Repository" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Remove existing remote if it exists
git remote remove origin -ErrorAction SilentlyContinue

$REMOTE_URL = "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/${GITHUB_REPO}.git"
git remote add origin $REMOTE_URL

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to add remote" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Remote repository added" -ForegroundColor Green

# Step 6: Push to GitHub
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "STEP 6: Push to GitHub" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

git branch -M main
git push -u origin main

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to push to GitHub" -ForegroundColor Red
    exit 1
}

# Success!
Write-Host "`n========================================" -ForegroundColor Green
Write-Host "✅ SUCCESS!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host "`nYour repository is now ready at:" -ForegroundColor Yellow
Write-Host "https://github.com/${GITHUB_USERNAME}/${GITHUB_REPO}" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Go to https://railway.app" -ForegroundColor White
Write-Host "2. Create new project" -ForegroundColor White
Write-Host "3. Add PostgreSQL service" -ForegroundColor White
Write-Host "4. Connect your GitHub repository" -ForegroundColor White
Write-Host "5. Set environment variables" -ForegroundColor White
Write-Host "6. Deploy!" -ForegroundColor White

Write-Host "`n⚠️  SECURITY REMINDER:" -ForegroundColor Red
Write-Host "Your GitHub token has been used in this script." -ForegroundColor Red
Write-Host "Please regenerate your token immediately:" -ForegroundColor Red
Write-Host "https://github.com/settings/tokens" -ForegroundColor Cyan

Write-Host "`n========================================" -ForegroundColor Cyan

Pop-Location
exit 0
