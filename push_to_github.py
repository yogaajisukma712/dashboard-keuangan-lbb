#!/usr/bin/env python3
"""
GitHub Push Script for Dashboard Keuangan LBB Super Smart
This script will push your Flask project to GitHub using your token
"""

import os
import subprocess
import sys
from pathlib import Path

# Configuration
GITHUB_USERNAME = "hnoivvs"
GITHUB_TOKEN = "YOUR_GITHUB_TOKEN_HERE"  # Replace with your token
GITHUB_REPO = "lbb-super-smart"
GITHUB_EMAIL = "admin@lbb-super-smart.com"


def run_command(cmd, cwd=None):
    """Run a shell command and return success status"""
    try:
        print(f"\n📝 Running: {cmd}")
        result = subprocess.run(
            cmd, shell=True, cwd=cwd, capture_output=True, text=True
        )

        if result.stdout:
            print(result.stdout)

        if result.returncode != 0:
            if result.stderr:
                print(f"❌ Error: {result.stderr}")
            return False

        print("✅ Success")
        return True
    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        return False


def main():
    """Main push function"""
    project_path = Path(__file__).parent

    print("\n" + "=" * 60)
    print("GitHub Push Script")
    print("Dashboard Keuangan LBB Super Smart")
    print("=" * 60)
    print(f"\nProject path: {project_path}")
    print(f"GitHub username: {GITHUB_USERNAME}")
    print(f"Repository: {GITHUB_REPO}")

    # Step 1: Configure git
    print("\n" + "=" * 60)
    print("STEP 1: Configure Git")
    print("=" * 60)

    if not run_command(f'git config user.name "LBB Super Smart"', project_path):
        print("Failed to set git username")
        return False

    if not run_command(f'git config user.email "{GITHUB_EMAIL}"', project_path):
        print("Failed to set git email")
        return False

    # Step 2: Initialize repository
    print("\n" + "=" * 60)
    print("STEP 2: Initialize Repository")
    print("=" * 60)

    git_dir = project_path / ".git"
    if git_dir.exists():
        print("⚠️  Repository already initialized, skipping init")
    else:
        if not run_command("git init", project_path):
            print("Failed to initialize git repository")
            return False

    # Step 3: Add all files
    print("\n" + "=" * 60)
    print("STEP 3: Add All Files")
    print("=" * 60)

    if not run_command("git add .", project_path):
        print("Failed to add files")
        return False

    # Step 4: Create commit
    print("\n" + "=" * 60)
    print("STEP 4: Create Commit")
    print("=" * 60)

    if not run_command(
        'git commit -m "Initial commit: Dashboard Keuangan LBB Super Smart - Ready for Railway deployment"',
        project_path,
    ):
        print("Note: Commit might have failed due to no changes, continuing...")

    # Step 5: Add remote
    print("\n" + "=" * 60)
    print("STEP 5: Add Remote Repository")
    print("=" * 60)

    # Remove existing remote if it exists
    run_command("git remote remove origin", project_path)

    remote_url = f"https://{GITHUB_USERNAME}:{GITHUB_TOKEN}@github.com/{GITHUB_USERNAME}/{GITHUB_REPO}.git"

    if not run_command(f'git remote add origin "{remote_url}"', project_path):
        print("Failed to add remote")
        return False

    # Step 6: Push to GitHub
    print("\n" + "=" * 60)
    print("STEP 6: Push to GitHub")
    print("=" * 60)

    # Rename branch to main
    run_command("git branch -M main", project_path)

    # Push to GitHub
    if not run_command("git push -u origin main", project_path):
        print("Failed to push to GitHub")
        return False

    # Success!
    print("\n" + "=" * 60)
    print("✅ SUCCESS!")
    print("=" * 60)
    print(f"\nYour repository is now ready at:")
    print(f"https://github.com/{GITHUB_USERNAME}/{GITHUB_REPO}")
    print("\nNext steps:")
    print("1. Go to https://railway.app")
    print("2. Create new project")
    print("3. Add PostgreSQL service")
    print("4. Connect your GitHub repository")
    print("5. Set environment variables")
    print("6. Deploy!")
    print("\n⚠️  SECURITY REMINDER:")
    print("Your GitHub token has been used in this script.")
    print("Please regenerate your token immediately:")
    print("https://github.com/settings/tokens")
    print("\n" + "=" * 60)

    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
