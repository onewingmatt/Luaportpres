#!/bin/bash
echo "=========================================="
echo "EMERGENCY: FORCE UPDATE"
echo "=========================================="

if [ ! -d ".git" ]; then
    echo "❌ NOT IN GIT REPO!"
    exit 1
fi

echo ""
echo "Current remote:"
git remote -v

echo ""
echo "Git log (last 5):"
git log --oneline -5

echo ""
echo "Adding all files..."
git add -A

echo "Committing..."
git commit -m "FORCE UPDATE: Game options implemented - $(date '+%Y-%m-%d %H:%M:%S')" || echo "Nothing to commit"

echo ""
echo "Force pushing to GitHub (overwrites any old versions)..."
git push --force-with-lease origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ FORCE PUSH SUCCESSFUL!"
    echo "✅ New version is now live"
    echo ""
    echo "Wait 2-3 minutes for Fly.io to redeploy..."
    echo "Then refresh: https://luaportpres.fly.dev"
else
    echo ""
    echo "❌ PUSH FAILED"
    echo "Try: git push --force origin main"
    exit 1
fi
