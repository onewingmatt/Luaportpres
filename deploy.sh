#!/bin/bash

# lua.zip Deploy Script for onewingmatt/Luaportpres
# SSH-based deployment (works with Google GitHub login)

echo "=========================================="
echo "DEPLOYING lua.zip TO GITHUB"
echo "=========================================="

# Repository info (hardcoded for your repo)
REPO_NAME="Luaportpres"
REPO_URL="git@github.com:onewingmatt/Luaportpres.git"

# Check if in repo directory
if [ ! -d ".git" ]; then
    echo ""
    echo "NOT IN A GIT REPO!"
    echo ""
    echo "First time setup:"
    echo "  cd ~"
    echo "  git clone $REPO_URL"
    echo "  cd $REPO_NAME"
    echo "  unzip ~/storage/downloads/lua.zip -y"
    echo "  bash deploy.sh"
    exit 1
fi

# Show what changed
echo ""
echo "Changes:"
git status --short

# Check for changes
if [ -z "$(git status --porcelain)" ]; then
    echo "No changes to deploy"
    exit 0
fi

# Stage all files
echo ""
echo "Staging files..."
git add .

# Commit with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
COMMIT_MSG="Mobile update: $TIMESTAMP"

echo "Committing: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

# Push to GitHub (SSH - no password needed)
echo ""
echo "Pushing to GitHub (SSH)..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SUCCESS!"
    echo "✓ Changes pushed to GitHub"
    echo "✓ Fly.io will auto-deploy"
    echo ""
    echo "Check deployment at:"
    echo "https://luaportpres.fly.dev"
    echo ""
else
    echo ""
    echo "✗ PUSH FAILED"
    echo ""
    echo "Troubleshooting:"
    echo "1. Check internet connection"
    echo "2. Verify SSH is working: ssh -T git@github.com"
    echo "3. Check SSH key on GitHub: https://github.com/settings/keys"
    exit 1
fi
