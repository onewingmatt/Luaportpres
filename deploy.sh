#!/bin/bash
if [ ! -d ".git" ]; then
    echo "NOT IN A GIT REPO!"
    exit 1
fi
git add .
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Options panel visible and accessible: $TIMESTAMP"
git push origin main
if [ $? -eq 0 ]; then
    echo "✓ Deployed to https://luaportpres.fly.dev"
else
    echo "✗ FAILED"
    exit 1
fi
