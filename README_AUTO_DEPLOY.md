# AUTO-DEPLOY SCRIPTS INCLUDED

## Files Included

✓ deploy.sh - Bash script for Termux (recommended)
✓ deploy.py - Python script (fallback)
✓ QUICK_START.md - 5-minute setup guide
✓ SETUP_GUIDE.md - Detailed setup instructions
✓ All game files (president.html, app.py, etc.)

## How to Use

### First Time (One-time Setup):
1. Install Termux app
2. Follow QUICK_START.md (5 minutes)
3. Extract this ZIP

### Every Deployment:
Just run: `bash deploy.sh`

That's it! Script handles:
✓ Git add (stage files)
✓ Git commit (with timestamp)
✓ Git push (to GitHub)
✓ Fly.io auto-deploys
✓ Shows success message

### Deployment Time: 60 seconds total

## What deploy.sh Does

1. Checks if in git repository
2. Shows what changed
3. Stages all files (git add .)
4. Commits with timestamp
5. Pushes to GitHub main branch
6. Confirms deployment

No more manual steps on GitHub website!

## Why This Is Better

Before (Your current process):
1. Download ZIP
2. Extract files
3. Go to GitHub website
4. Upload files manually
5. Commit manually
6. Trigger deploy on Fly.io
7. Test
Total: 10-15 minutes

After (With this script):
1. Extract ZIP
2. Run: bash deploy.sh
3. Test
Total: 60 seconds

## Requirements

- Termux app (free)
- Git installed (one command: apt install git)
- SSH keys set up (one-time, ~2 minutes)

## Support

If deploy.sh fails:
- Try deploy.py (Python version)
- Check your internet
- Verify SSH/GitHub credentials
- See SETUP_GUIDE.md for troubleshooting
