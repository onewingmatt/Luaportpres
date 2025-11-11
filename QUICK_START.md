# QUICK START (First Time)

## 1. Install Termux (Free Android App)
- Download from F-Droid (recommended)
- Or Google Play Store

## 2. Setup (5 minutes, one time only)

```
apt update && apt install git openssh

# SSH setup (recommended):
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub
# Copy output and add to https://github.com/settings/keys

# Clone your repo:
git clone git@github.com:yourusername/luaportpres.git
cd luaportpres
```

## 3. Extract ZIP and Copy Files

- Extract ZIP to Termux folder
- Copy: president.html, app.py, requirements.txt, fly.toml

## 4. Deploy (Every time you get updates)

```
bash deploy.sh
```

## That's It!

Fly.io auto-deploys from GitHub
Check: https://luaportpres.fly.dev
