#!/usr/bin/env python3
"""
Auto-deploy script for Android (Python version)
Usage: python3 deploy.py
"""

import subprocess
import sys
from datetime import datetime

def run_command(cmd, description):
    """Run a git command and handle errors"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"ERROR: {result.stderr}")
            return False
        if result.stdout:
            print(result.stdout.strip())
        return True
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("="*50)
    print("LUAPORTPRES AUTO-DEPLOY SCRIPT")
    print("="*50)

    # Check if in git repo
    if not run_command("git rev-parse --git-dir > /dev/null 2>&1", "Checking git repository"):
        print("ERROR: Not in a git repository")
        print("Please make sure you're in the luaportpres folder")
        sys.exit(1)

    # Show status
    print("\nCurrent git status:")
    run_command("git status --short", "")

    # Check for changes
    result = subprocess.run("git status --porcelain", shell=True, capture_output=True, text=True)
    if not result.stdout.strip():
        print("\nNo changes to commit")
        sys.exit(0)

    # Stage all changes
    if not run_command("git add .", "Staging files"):
        sys.exit(1)

    # Show what will be committed
    print("\nFiles to commit:")
    run_command("git status --short", "")

    # Commit
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Mobile update: {timestamp}"

    if not run_command(f'git commit -m "{commit_msg}"', "Committing changes"):
        print("No changes to commit")
        sys.exit(0)

    # Push
    if not run_command("git push origin main", "Pushing to GitHub"):
        print("\nFailed to push. Check your:")
        print("- Internet connection")
        print("- SSH keys (if using SSH)")
        print("- GitHub token (if using HTTPS)")
        sys.exit(1)

    print("\n" + "="*50)
    print("✓ SUCCESS!")
    print("="*50)
    print("Changes pushed to GitHub")
    print("Fly.io will auto-deploy from latest commit")
    print("\nCheck deployment at: https://luaportpres.fly.dev")

if __name__ == "__main__":
    main()
