#!/bin/bash

# GitHub Push Setup Script for Flask Dashboard Keuangan LBB Super Smart
# This script will configure git and push your project to GitHub

echo "=========================================="
echo "GitHub Push Setup Script"
echo "Dashboard Keuangan LBB Super Smart"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if git is installed
if ! command -v git &> /dev/null; then
    echo "❌ Git is not installed. Please install Git first."
    exit 1
fi

echo -e "${BLUE}Step 1: Git Configuration${NC}"
echo "Setting up git user..."
git config user.name "LBB Super Smart" 2>/dev/null || true
git config user.email "admin@lbb-super-smart.com" 2>/dev/null || true
echo "✅ Git configured"
echo ""

echo -e "${BLUE}Step 2: Initialize Repository${NC}"
if [ -d .git ]; then
    echo "⚠️  Repository already initialized"
else
    git init
    echo "✅ Repository initialized"
fi
echo ""

echo -e "${BLUE}Step 3: Add All Files${NC}"
git add .
echo "✅ All files added to staging"
echo ""

echo -e "${BLUE}Step 4: Create Initial Commit${NC}"
git commit -m "Initial commit: Dashboard Keuangan LBB Super Smart - Ready for Railway deployment" 2>/dev/null || echo "⚠️  Nothing new to commit"
echo "✅ Commit created"
echo ""

echo -e "${BLUE}Step 5: Get Repository Information${NC}"
echo ""
echo "To complete the GitHub setup, you need to:"
echo ""
echo "1. Create a new repository on GitHub:"
echo "   - Go to: https://github.com/new"
echo "   - Repository name: lbb-super-smart (or your preferred name)"
echo "   - Description: Dashboard Keuangan Lembaga Bimbingan Belajar"
echo "   - Choose: Public or Private"
echo "   - Click: Create repository"
echo ""
echo "2. Then run this command (replace with your GitHub username and repo name):"
echo ""
echo -e "${YELLOW}git remote add origin https://YOUR_USERNAME:YOUR_TOKEN@github.com/YOUR_USERNAME/lbb-super-smart.git${NC}"
echo ""
echo "3. Push to GitHub:"
echo ""
echo -e "${YELLOW}git branch -M main${NC}"
echo -e "${YELLOW}git push -u origin main${NC}"
echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="
echo ""
echo "⚠️  IMPORTANT SECURITY NOTE:"
echo "Your GitHub token has been shown in plain text."
echo "Consider regenerating it after this push:"
echo "https://github.com/settings/tokens"
echo ""
