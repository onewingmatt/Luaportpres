# TROUBLESHOOTING: Why Options Keep Reverting

## Problem
The game keeps reverting to old version without options.

## Causes
1. Old commits in git history
2. Fly.io caching old version
3. Git branch issues

## Solutions

### Option 1: FORCE PUSH (Recommended)
```bash
cd ~/Luaportpres
git push --force-with-lease origin main
```

This overwrites ANY old commits with current version.

### Option 2: Full Reset
```bash
cd ~/Luaportpres
git reset --hard HEAD~5
git push --force origin main
```

Resets last 5 commits and force pushes.

### Option 3: Check What's Deployed
```bash
git log --oneline -10
# Shows last 10 commits
# Latest should have "Game options"

git show HEAD:president.html | grep "optNumPlayers"
# Should return match if options are there
```

### Option 4: Fly.io Cache
If deployed but still old on website:
- Go to Fly.io dashboard
- Redeploy or restart app
- Clear browser cache (Ctrl+F5)

## After Deploying

1. Check git log shows correct commit
2. Wait 2-3 minutes for Fly.io
3. Go to https://luaportpres.fly.dev
4. Refresh page (Ctrl+F5)
5. Scroll down - should see options

## What to Look For

On the page, after Create Game section, you should see:
- "⚙️ Game Options" header
- 4 dropdown fields
- 7 checkboxes

If NOT there after 5 minutes: Something is still wrong.
