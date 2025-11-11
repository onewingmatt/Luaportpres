#!/bin/bash
echo "=========================================="
echo "DEPLOYING COMPLETE OPTIONS UPDATE"
echo "=========================================="

if [ ! -d ".git" ]; then
    echo "NOT IN A GIT REPO!"
    exit 1
fi

echo ""
echo "Git status:"
git status --short

echo ""
echo "Adding all files..."
git add .

echo "Committing..."
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Complete: All TIC-80 options implemented - $TIMESTAMP"

echo ""
echo "Pushing to GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SUCCESS!"
    echo "✅ All options deployed"
    echo "✅ Check https://luaportpres.fly.dev"
    echo ""
else
    echo ""
    echo "❌ PUSH FAILED"
    exit 1
fi
