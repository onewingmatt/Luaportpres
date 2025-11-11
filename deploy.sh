#!/bin/bash
if [ ! -d ".git" ]; then
    echo "NOT IN GIT REPO!"
    exit 1
fi
git add -A
git commit -m "Clean: Remove play log box - $(date '+%Y-%m-%d %H:%M:%S')"
git push --force-with-lease origin main
if [ $? -eq 0 ]; then
    echo "✅ DEPLOYED!"
else
    echo "❌ FAILED"
    exit 1
fi
