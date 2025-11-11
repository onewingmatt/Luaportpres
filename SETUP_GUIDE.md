# ANDROID AUTO-DEPLOY SETUP GUIDE

## Prerequisites

**Option A: Using Termux (Recommended)**
1. Download Termux app from F-Droid (free)
2. Open Termux and run:
   ```
   apt update
   apt install git openssh
   ```
3. Generate SSH keys (one time):
   ```
   ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
   cat ~/.ssh/id_ed25519.pub
   ```
4. Add SSH key to GitHub:
   - Go to github.com/settings/keys
   - Click "New SSH key"
   - Paste the key output from above
   - Save

**Option B: Using Git Credentials (Simpler)**
1. Install Termux
2. Install git: `apt install git`
3. Configure git:
   ```
   git config --global user.name "Your Name"
   git config --global user.email "your@email.com"
   git config --global credential.helper store
   ```
4. First push will ask for GitHub token
   - Generate token at: github.com/settings/tokens
   - Use token as password (only once, then cached)

## Setup Your Project (One Time)

1. Extract this ZIP
2. Open Termux
3. Navigate to folder:
   ```
   cd /path/to/extracted/luaportpres
   ```
4. Clone your repo (or use existing):
   ```
   cd ..
   git clone git@github.com:yourusername/luaportpres.git
   cd luaportpres
   ```
5. Copy files from extracted folder into this directory

## Deploy Your Changes

### Option 1: Using Bash Script (Fastest)

```
bash deploy.sh
```

That's it! Script will:
- Show what changed
- Stage files
- Commit with timestamp
- Push to GitHub
- Auto-deploy on Fly.io

### Option 2: Using Python Script

```
python3 deploy.py
```

Same as bash script, but using Python

### Option 3: Manual Commands

```
git add .
git commit -m "Mobile update: $(date)"
git push origin main
```

## Troubleshooting

**"Permission denied" on deploy script:**
```
chmod +x deploy.sh
bash deploy.sh
```

**"Not in a git repository":**
- Make sure you're in the correct folder
- Check: `ls -la | grep .git`

**"Failed to push":**
- Check internet connection
- Check SSH keys are set up
- Or use git credentials instead of SSH

**"Git command not found":**
```
apt install git
```

## Workflow

1. Get ZIP from AI assistant
2. Extract to your Termux working folder
3. Copy files
4. Run `bash deploy.sh`
5. Done! Game deploys automatically

From download to deployed: **60 seconds**
