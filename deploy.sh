#!/bin/bash

# Auto-deploy script for Termux on Android
# Usage: bash deploy.sh

echo "=========================================="
echo "LUAPORTPRES AUTO-DEPLOY SCRIPT"
echo "=========================================="

# Check if we're in a git repository
if [ ! -d ".git" ]; then
    echo "ERROR: Not in a git repository"
    echo "Please make sure you're in the luaportpres folder"
    exit 1
fi

# Get status
echo ""
echo "Git status:"
git status --short

# Check for changes
if [ -z "$(git status --porcelain)" ]; then
    echo ""
    echo "No changes to commit"
    exit 0
fi

# Stage all changes
echo ""
echo "Staging files..."
git add .

# Show what will be committed
echo ""
echo "Files to commit:"
git status --short

# Commit with timestamp
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
COMMIT_MSG="Mobile update: $TIMESTAMP"

echo ""
echo "Committing with message: $COMMIT_MSG"
git commit -m "$COMMIT_MSG"

# Push to origin
echo ""
echo "Pushing to GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SUCCESS! Changes pushed to GitHub"
    echo "✓ Fly.io will auto-deploy from latest commit"
    echo ""
    echo "Check deployment at: https://luaportpres.fly.dev"
else
    echo ""
    echo "✗ FAILED to push. Check your internet connection."
    echo "You may need to set up SSH keys or GitHub token"
    exit 1
fi
