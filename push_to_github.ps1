# GitHub Push Setup Script for Flask Dashboard Keuangan LBB Super Smart
# This script will configure git and push your project to GitHub using your token
# Run this script from the app_lembaga directory

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "GitHub Push Setup Script" -ForegroundColor Cyan
Write-Host "Dashboard Keuangan LBB Super Smart" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check if git is installed
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: Git is not installed. Please install Git first." -ForegroundColor Red
    Write-Host "Download from: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# GitHub Token - REPLACE WITH YOUR OWN TOKEN
$GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"

Write-Host "Step 1: Git Configuration" -ForegroundColor Blue
Write-Host "Setting up git user..." -ForegroundColor White
git config user.name "LBB Super Smart" 2>$null
git config user.email "admin@lbb-super-smart.com" 2>$null
Write-Host "✓ Git configured" -ForegroundColor Green
Write-Host ""

Write-Host "Step 2: Initialize Repository" -ForegroundColor Blue
if (Test-Path ".git" -PathType Container) {
    Write-Host "⚠ Repository already initialized" -ForegroundColor Yellow
} else {
    git init
    Write-Host "✓ Repository initialized" -ForegroundColor Green
}
Write-Host ""

Write-Host "Step 3: Add All Files" -ForegroundColor Blue
git add .
Write-Host "✓ All files added to staging" -ForegroundColor Green
Write-Host ""

Write-Host "Step 4: Create Initial Commit" -ForegroundColor Blue
git commit -m "Initial commit: Dashboard Keuangan LBB Super Smart - Ready for Railway deployment" 2>$null
Write-Host "✓ Commit created" -ForegroundColor Green
Write-Host ""

Write-Host "Step 5: GitHub Setup Instructions" -ForegroundColor Blue
Write-Host ""
Write-Host "REQUIRED: Create GitHub Repository First!" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Go to: https://github.com/new" -ForegroundColor White
Write-Host "   - Repository name: lbb-super-smart" -ForegroundColor Cyan
Write-Host "   - Description: Dashboard Keuangan Lembaga Bimbingan Belajar" -ForegroundColor Cyan
Write-Host "   - Choose: Public (recommended for Railway)" -ForegroundColor Cyan
Write-Host "   - Click: 'Create repository'" -ForegroundColor Cyan
Write-Host ""

Write-Host "2. Once repository is created, enter your GitHub username:" -ForegroundColor White
$GITHUB_USERNAME = Read-Host "GitHub Username"

if ([string]::IsNullOrWhiteSpace($GITHUB_USERNAME)) {
    Write-Host "ERROR: GitHub username cannot be empty" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "Step 6: Add Remote Repository" -ForegroundColor Blue
$REMOTE_URL = "https://${GITHUB_USERNAME}:${GITHUB_TOKEN}@github.com/${GITHUB_USERNAME}/lbb-super-smart.git"
Write-Host "Adding remote origin..." -ForegroundColor White

# Remove existing remote if it exists
git remote remove origin 2>$null

# Add new remote with token
git remote add origin $REMOTE_URL

Write-Host "✓ Remote repository added" -ForegroundColor Green
Write-Host ""

Write-Host "Step 7: Push to GitHub" -ForegroundColor Blue
Write-Host "Pushing code to GitHub..." -ForegroundColor White

# Rename branch to main
git branch -M main

# Push to GitHub
git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Code pushed to GitHub successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "SUCCESS!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Your repository is now ready for Railway deployment!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor White
    Write-Host "1. Go to: https://railway.app" -ForegroundColor Cyan
    Write-Host "2. Create new project" -ForegroundColor Cyan
    Write-Host "3. Add PostgreSQL service" -ForegroundColor Cyan
    Write-Host "4. Connect your GitHub repository" -ForegroundColor Cyan
    Write-Host "5. Set environment variables" -ForegroundColor Cyan
    Write-Host "6. Deploy!" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Repository URL: https://github.com/${GITHUB_USERNAME}/lbb-super-smart" -ForegroundColor Yellow
    Write-Host ""
} else {
    Write-Host "ERROR: Failed to push to GitHub" -ForegroundColor Red
    Write-Host "Please check your GitHub token and repository settings" -ForegroundColor Yellow
    exit 1
}

Write-Host "IMPORTANT SECURITY NOTE:" -ForegroundColor Yellow
Write-Host "Your GitHub token has been used in this script." -ForegroundColor White
Write-Host "After successful deployment, consider regenerating your token:" -ForegroundColor White
Write-Host "https://github.com/settings/tokens" -ForegroundColor Cyan
Write-Host ""
