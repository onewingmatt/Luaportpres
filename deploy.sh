#!/bin/bash
if [ ! -d ".git" ]; then
    echo "NOT IN A GIT REPO!"
    exit 1
fi
git add .
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
git commit -m "Fix: game not found bug + UI cleanup: $TIMESTAMP"
git push origin main
if [ $? -eq 0 ]; then
    echo "✓ Deployed!"
else
    echo "✗ FAILED"
    exit 1
fi
