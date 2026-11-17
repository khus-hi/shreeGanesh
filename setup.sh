#!/usr/bin/env bash
# One-time setup: stores your keys as GitHub secrets on this repo and starts the first scan.
# After this, everything runs on its own every hour.
#
# Needs the GitHub CLI (https://cli.github.com)  ->  Mac: brew install gh
# Run from inside the cloned repo:   bash setup.sh
set -e
cd "$(dirname "$0")"

command -v gh >/dev/null || { echo "Install the GitHub CLI first: https://cli.github.com (Mac: brew install gh)"; exit 1; }
gh auth status >/dev/null 2>&1 || gh auth login

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "khus-hi/shreeGanesh")
echo "Setting up $REPO"

read -rp "SerpAPI key (from serpapi.com): " SERPAPI_KEY
read -rsp "Claude API key (optional, press Enter to skip resume tailoring): " ANTHROPIC_API_KEY; echo
read -rp "Gmail address: " GMAIL_USER
read -rsp "Gmail app password (input hidden): " GMAIL_APP_PASSWORD; echo
read -rp "Send alerts to [$GMAIL_USER]: " ALERT_EMAIL_TO; ALERT_EMAIL_TO=${ALERT_EMAIL_TO:-$GMAIL_USER}

gh secret set SERPAPI_KEY        -R "$REPO" --body "$SERPAPI_KEY"
if [ -n "$ANTHROPIC_API_KEY" ]; then
  gh secret set ANTHROPIC_API_KEY -R "$REPO" --body "$ANTHROPIC_API_KEY"
else
  echo "No Claude key: skipping resume tailoring (everything else still runs)."
fi
gh secret set GMAIL_USER         -R "$REPO" --body "$GMAIL_USER"
gh secret set GMAIL_APP_PASSWORD -R "$REPO" --body "$GMAIL_APP_PASSWORD"
gh secret set ALERT_EMAIL_TO     -R "$REPO" --body "$ALERT_EMAIL_TO"

gh workflow enable scan.yml -R "$REPO" >/dev/null 2>&1 || true
gh workflow run scan.yml -R "$REPO" && echo "First scan started."
echo
echo "Done. It runs every hour on its own; new jobs are emailed to $ALERT_EMAIL_TO."
echo "Watch runs: gh run list -R $REPO --workflow scan.yml   (or the Actions tab on GitHub)"
