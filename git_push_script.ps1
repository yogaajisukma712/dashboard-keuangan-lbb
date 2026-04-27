# Add Git to PATH
$env:PATH += ";C:\Program Files\Git\cmd"

# Navigate to project directory
Set-Location "C:\Users\desip\OneDrive\Documents\Lembaga\App Lembaga\app_lembaga"

Write-Host "=== GIT SETUP & PUSH TO GITHUB ===" -ForegroundColor Cyan
Write-Host ""

# Step 1: Configure Git user
Write-Host "Step 1: Configuring Git user..." -ForegroundColor Yellow
git config user.name "LBB Super Smart"
Write-Host "User name configured" -ForegroundColor Green

git config user.email "admin@lbb-super-smart.com"
Write-Host "User email configured" -ForegroundColor Green
Write-Host ""

# Step 2: Initialize repository
Write-Host "Step 2: Initializing Git repository..." -ForegroundColor Yellow
git init
Write-Host "Repository initialized" -ForegroundColor Green
Write-Host ""

# Step 3: Add all files
Write-Host "Step 3: Adding all files to Git..." -ForegroundColor Yellow
git add .
Write-Host "All files added" -ForegroundColor Green
Write-Host ""

# Step 4: Create initial commit
Write-Host "Step 4: Creating initial commit..." -ForegroundColor Yellow
git commit -m "Initial commit: Dashboard Keuangan LBB Super Smart - Ready for Railway deployment"
Write-Host "Initial commit created" -ForegroundColor Green
Write-Host ""

# Step 5: Add remote repository
Write-Host "Step 5: Adding remote repository..." -ForegroundColor Yellow
git remote remove origin
git remote add origin "https://github.com/hnoivvs/lbb-super-smart.git"
Write-Host "Remote repository added" -ForegroundColor Green
Write-Host ""

# Step 6: Rename branch to main
Write-Host "Step 6: Renaming branch to main..." -ForegroundColor Yellow
git branch -M main
Write-Host "Branch renamed to main" -ForegroundColor Green
Write-Host ""

# Step 7: Push to GitHub
Write-Host "Step 7: Pushing to GitHub..." -ForegroundColor Yellow
Write-Host "Note: You will be prompted for your credentials" -ForegroundColor Yellow
git push -u origin main
Write-Host "Successfully pushed to GitHub" -ForegroundColor Green
Write-Host ""

Write-Host "=== SUCCESS ===" -ForegroundColor Green
Write-Host "Repository: https://github.com/hnoivvs/lbb-super-smart" -ForegroundColor Cyan
