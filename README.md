# Philosophy Bot — repo notes for deployment & secrets cleanup

This repository contains a Telegram polling bot. Important deployment and security notes:

1) Environment variables
- Don't store secrets in the repo. Use Render's Environment settings (or your host's secret manager) to set:
  - TELEGRAM_BOT_TOKEN
  - OPENAI_API_KEY

2) Render deployment (recommended)
- Use a Background Worker service (not a Web service) since the bot runs a long-lived polling process.
- Start command: `python bot.py` (the repository includes `bot.py` which runs the main script).
- Ensure `requirements.txt` is present (it is).

3) Filename with spaces
- The original script filename `python philosophy_bot.py` contains spaces and is awkward to call directly in some platforms.
- `bot.py` is a small wrapper that runs the original script. Use `python bot.py` as the start command.

4) Removing leaked secrets from git history
- If you accidentally committed secrets (API keys, tokens), rotate them immediately.
- A `replacements.txt` file is included mapping the known leaked values to `REDACTED_*` placeholders for git-filter-repo.
- To fully remove secrets from history and force-push the cleaned history, run `cleanup_history.ps1` from an elevated PowerShell (Run as Administrator). This script:
  1. Creates a mirror backup: `..\bottt-mirror-backup.git`
  2. Installs `git-filter-repo`
  3. Runs `git-filter-repo --replace-text replacements.txt --force`
  4. Runs garbage collection and force-pushes `main` to the origin

5) After history rewrite
- Rotate all affected credentials and update Render's environment variables with the new tokens.
- Inform collaborators: they must re-clone the repo after a history rewrite.

6) Troubleshooting
- If `git-filter-repo` prompts about deleting `.git/objects/*` directories due to permission errors on Windows, re-run the cleanup in an Administrator PowerShell.

If you'd like, I can also:
- Create a small HTTP health endpoint so the bot can be deployed as a Web Service (not recommended), or
- Rename the main file in-place (I kept the original file intact and added a safe wrapper).
