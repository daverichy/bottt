# cleanup_history.ps1
# Run this from the repository root using an elevated PowerShell (Run as Administrator).
# This script creates a mirror backup, runs git-filter-repo to redact secrets using
# replacements.txt, finishes cleanup, re-adds origin and force-pushes the cleaned history.

param(
    [string]$RemoteUrl = "https://github.com/daverichy/bottt.git"
)

Write-Host "[1/7] Creating a mirror backup of the repository..."
git clone --mirror . "..\bottt-mirror-backup.git"

Write-Host "[2/7] Installing or upgrading git-filter-repo (python package)..."
python -m pip install --upgrade git-filter-repo

Write-Host "[3/7] Running git-filter-repo to replace secrets (uses replacements.txt)..."
# Use python -m git_filter_repo to avoid path issues
python -m git_filter_repo --replace-text replacements.txt --force

Write-Host "[4/7] Expire reflog and garbage-collect to remove old objects..."
git reflog expire --expire=now --all
git gc --prune=now --aggressive

Write-Host "[5/7] Re-adding origin remote (if missing) and verifying remote URL..."
if (git remote get-url origin 2>$null) {
    Write-Host "origin already exists; setting URL to $RemoteUrl"
    git remote set-url origin $RemoteUrl
} else {
    Write-Host "adding origin -> $RemoteUrl"
    git remote add origin $RemoteUrl
}

Write-Host "[6/7] Force-pushing cleaned history to origin/main (will rewrite remote history)."
Write-Host "IMPORTANT: This overwrites remote history. Ensure collaborators are informed."
git push --force origin main

Write-Host "[7/7] Done."
Write-Host "NEXT: Rotate any exposed credentials immediately (OpenAI, Telegram)."
Write-Host "Inform collaborators that history was rewritten. They should re-clone the repo."
