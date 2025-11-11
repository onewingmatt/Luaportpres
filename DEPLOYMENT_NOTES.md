# lua.zip Deployment Package

## What's Included

✓ president.html - Game UI (with play log inline + game_id tracking)
✓ app.py - Backend (fixed game creation bug)
✓ requirements.txt - Python dependencies
✓ fly.toml - Fly.io configuration
✓ deploy.sh - Auto-deploy script (SSH-based)
✓ QUICK_START.md - Setup guide
✓ DEPLOYMENT_NOTES.md - This file

## Game Fixes Included

✓ Play Log moved from floating to inline (no more black box)
✓ Game creation bug fixed (game_id tracking + socket emit)
✓ Visual design preserved (purple gradient, Segoe UI)
✓ All buttons working (Play, Clear, Pass)

## Deploy Workflow

### First Time
```bash
cd ~
git clone git@github.com:onewingmatt/Luaportpres.git
cd Luaportpres
unzip ~/storage/downloads/lua.zip -y
bash deploy.sh
```

### Every Update
```bash
cd ~/Luaportpres
unzip ~/storage/downloads/lua.zip -y
bash deploy.sh
```

That's it!

## SSH Setup (One-Time)

```bash
# Generate key
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Show key
cat ~/.ssh/id_ed25519.pub

# Add to GitHub: https://github.com/settings/keys

# Test
ssh -T git@github.com
```

## Why This Works

✓ SSH uses cryptographic keys (no passwords)
✓ Works with Google GitHub login
✓ No password prompts after setup
✓ Automatic push to GitHub
✓ Fly.io auto-deploys
✓ 60 seconds from download to live

## Support

See QUICK_START.md for troubleshooting and detailed instructions.

Good luck! 🚀
