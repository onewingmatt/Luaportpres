# lua.zip - Quick Start Guide

## First Time Setup (One-time, 5 minutes)

### 1. Install Termux (Free Android App)
- Download from F-Droid or Google Play

### 2. In Termux, run these commands:

```bash
# Update packages
apt update

# Install git and openssh
apt install git openssh

# Generate SSH key
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Show your public key (COPY THIS)
cat ~/.ssh/id_ed25519.pub
```

### 3. Add SSH Key to GitHub

1. Go to: https://github.com/settings/keys
2. Click "New SSH key"
3. Title: "Termux on Android"
4. Paste the key from above
5. Click "Add SSH key"

### 4. Test SSH

```bash
ssh -T git@github.com
# Should say: "Hi onewingmatt! You've successfully authenticated..."
```

### 5. Clone Your Repo

```bash
cd ~
git clone git@github.com:onewingmatt/Luaportpres.git
cd Luaportpres
```

**You only do this once!**

---

## Every Time You Get lua.zip

### 1. Download lua.zip to your phone

### 2. In Termux:

```bash
# Grant storage access (first time)
termux-setup-storage

# Navigate to your repo
cd ~/Luaportpres

# Extract the ZIP (overwrites old files)
unzip ~/storage/downloads/lua.zip -y

# Deploy!
bash deploy.sh
```

**That's it! From download to deployed: 60 seconds**

---

## What deploy.sh Does

✓ Shows what changed
✓ Stages all files (git add)
✓ Commits with timestamp
✓ Pushes to GitHub (SSH - no password!)
✓ Fly.io auto-deploys
✓ Shows success message

---

## Troubleshooting

**SSH not working?**
```bash
ssh -T git@github.com
# Should say "Hi onewingmatt!..."
```

**SSH key not found?**
```bash
# Regenerate it
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""

# Add to GitHub again: https://github.com/settings/keys
```

**Stuck in deploy script?**
```bash
# Press Ctrl+C to stop

# Try manually:
cd ~/Luaportpres
git status
git add .
git commit -m "manual update"
git push origin main
```

**Can't see lua.zip in Termux?**
```bash
# Grant storage access first
termux-setup-storage

# Then check
ls ~/storage/downloads/
```

---

## Your GitHub Login Uses Google?

No problem! SSH works with Google login because it uses cryptographic keys, not passwords.

Just make sure your SSH key is added to: https://github.com/settings/keys

---

## Summary

**Setup:** 5 minutes (one-time)
**Deploy:** 60 seconds (every time)
**No password prompts:** Ever!

Happy deploying! 🚀
