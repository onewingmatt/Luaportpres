#!/bin/bash
echo "=========================================="
echo "DEPLOYING GAME OPTIONS UPDATE"
echo "=========================================="
if [ ! -d ".git" ]; then
    echo "NOT IN A GIT REPO!"
    exit 1
fi
echo ""
echo "Changes:"
git status --short
if [ -z "$(git status --porcelain)" ]; then
    echo "No changes"
    exit 0
fi
git add .
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Game options implementation: $TIMESTAMP"
git push origin main
if [ $? -eq 0 ]; then
    echo ""
    echo "✓ SUCCESS! Check https://luaportpres.fly.dev"
else
    echo "✗ FAILED"
    exit 1
fi
