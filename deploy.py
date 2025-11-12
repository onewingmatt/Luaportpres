#!/usr/bin/env python3
"""
One-Command Deploy Script
Automatically deploys d:\temp\lua.zip with smart date+time commit message
Just run: python deploy.py
"""

import os
import sys
import zipfile
import subprocess
from datetime import datetime
from pathlib import Path

class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

def log(msg, color=Colors.BLUE):
    print(f"{color}{msg}{Colors.END}")

def log_step(msg):
    log(f"[*] {msg}", Colors.YELLOW)

def log_ok(msg):
    log(f"[+] {msg}", Colors.GREEN)

def log_err(msg):
    log(f"[!] {msg}", Colors.RED)

def run_cmd(cmd, desc=""):
    if desc:
        log_step(desc)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout.strip())
    return result.returncode == 0, result

def get_smart_message():
    """Generate time-based commit message with date"""
    now = datetime.now()
    hour = now.hour

    # Time periods with messages
    if 0 <= hour < 5:
        time_msg = "Late night update"
    elif 5 <= hour < 12:
        time_msg = "Morning push"
    elif 12 <= hour < 17:
        time_msg = "Afternoon update"
    elif 17 <= hour < 21:
        time_msg = "Evening release"
    else:
        time_msg = "Night owl coding"

    # Format: "Update: Dec 12, 8:14 AM - Late night update"
    date_str = now.strftime("%b %d")
    time_str = now.strftime("%I:%M %p").lstrip('0')  # Remove leading 0 from hour
    msg = f"Update: {date_str}, {time_str} - {time_msg}"

    return msg

def main():
    log("=" * 70, Colors.YELLOW)
    log("ONE-COMMAND DEPLOY SCRIPT", Colors.YELLOW)
    log("=" * 70, Colors.YELLOW)
    print()

    # Hard-coded paths
    ZIP_FILE = "d:\\temp\\lua.zip" if os.name == 'nt' else "/tmp/lua.zip"
    REPO_DIR = "D:\\dev\\Luaportpres" if os.name == 'nt' else os.path.expanduser("~/Luaportpres")

    # Normalize for current OS
    if os.name == 'nt':
        ZIP_FILE = ZIP_FILE.replace("\\", "\\")
        REPO_DIR = REPO_DIR.replace("\\", "\\")

    # Check ZIP exists
    if not os.path.isfile(ZIP_FILE):
        log_err(f"ZIP file not found: {ZIP_FILE}")
        log_err("Make sure lua.zip is in d:\\temp\\")
        sys.exit(1)

    log_ok(f"ZIP file found: {ZIP_FILE}")
    print()

    # Extract
    log_step(f"Extracting to {REPO_DIR}...")
    try:
        with zipfile.ZipFile(ZIP_FILE, 'r') as z:
            z.extractall(REPO_DIR)
        log_ok("Extracted successfully")
    except Exception as e:
        log_err(f"Extraction failed: {e}")
        sys.exit(1)

    # Touch files
    log_step("Updating file timestamps...")
    try:
        for root, dirs, files in os.walk(REPO_DIR):
            # Skip .git directory
            if '.git' in dirs:
                dirs.remove('.git')
            for file in files:
                filepath = os.path.join(root, file)
                os.utime(filepath, None)
        log_ok("Timestamps updated")
    except Exception as e:
        log_err(f"Failed to update timestamps: {e}")

    # Remove ZIP
    log_step("Cleaning up ZIP file...")
    try:
        os.remove(ZIP_FILE)
        log_ok("ZIP removed")
    except Exception as e:
        log_err(f"Failed to remove ZIP: {e}")

    print()

    # Change to repo
    os.chdir(REPO_DIR)

    # Generate smart message
    commit_msg = get_smart_message()
    log_ok(f"Generated message: {commit_msg}")
    print()

    # Git operations
    log_step("Staging files...")
    success, _ = run_cmd("git add -A")
    if not success:
        log_err("Failed to stage files")
        sys.exit(1)
    log_ok("Files staged")
    print()

    # Try commit
    log_step(f"Committing...")
    success, result = run_cmd(f'git commit -m "{commit_msg}"')

    if not success:
        if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
            log("No changes - using --allow-empty commit")
            success, result = run_cmd(f'git commit --allow-empty -m "{commit_msg}"')
            if success:
                log_ok("Empty commit created")
            else:
                log_err("Empty commit failed")
                sys.exit(1)
        else:
            log_err("Commit failed")
            sys.exit(1)
    else:
        log_ok("Changes committed")

    print()

    # Push
    log_step("Pushing to GitHub...")
    success, result = run_cmd("git push origin main")
    if success:
        log_ok("Pushed to GitHub")
    else:
        log_err("Push failed")
        sys.exit(1)

    print()
    log("=" * 70, Colors.GREEN)
    log("🎉 Deploy complete!", Colors.GREEN)
    log("=" * 70, Colors.GREEN)
    print()

if __name__ == "__main__":
    main()
