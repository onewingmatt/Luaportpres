#!/bin/bash
if [ ! -d ".git" ]; then
    echo "NOT IN A GIT REPO!"
    exit 1
fi
git add .
git commit -m "Rewrite: proper options implementation - $(date '+%Y-%m-%d %H:%M:%S')"
git push origin main
if [ $? -eq 0 ]; then
    echo "✓ Deployed to https://luaportpres.fly.dev"
else
    echo "✗ Deploy failed"
    exit 1
fi
