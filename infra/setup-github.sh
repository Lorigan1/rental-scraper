#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────
# Create GitHub repo and push rental-scraper project
#
# Prerequisites:
#   - gh CLI authenticated (gh auth login)
#
# Usage:
#   cd rental-scraper
#   bash infra/setup-github.sh
# ──────────────────────────────────────────────────────────────
set -euo pipefail

REPO_NAME="${GITHUB_REPO_NAME:-rental-scraper}"
VISIBILITY="${GITHUB_VISIBILITY:-public}"

echo "═══════════════════════════════════════════════════"
echo "  GitHub Setup — ${REPO_NAME}"
echo "═══════════════════════════════════════════════════"

# Initialize git if needed
if [ ! -d .git ]; then
    echo "→ Initializing git repository..."
    git init
    git branch -M main
fi

# Create GitHub repo
echo "→ Creating GitHub repository..."
gh repo create "${REPO_NAME}" \
    --"${VISIBILITY}" \
    --description "Vancouver rental market analysis tool — multi-source listing scraper" \
    --source=. \
    --remote=origin \
    --push 2>/dev/null || {
        echo "  Repo may already exist. Setting remote..."
        GITHUB_USER=$(gh api user --jq '.login')
        git remote add origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git" 2>/dev/null || \
            git remote set-url origin "https://github.com/${GITHUB_USER}/${REPO_NAME}.git"
    }

# Stage all files
echo "→ Staging files..."
git add -A

# Commit
echo "→ Creating initial commit..."
git commit -m "Initial commit: Vancouver rental scraper MVP

Multi-source rental listing scraper for market analysis.
- Craigslist, Kijiji, and Facebook Groups scrapers
- Unified Listing data model
- Cloud Run + Cloud SQL + GCS deployment config
- 38 unit tests passing

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>" 2>/dev/null || echo "  (nothing to commit)"

# Push
echo "→ Pushing to GitHub..."
git push -u origin main 2>/dev/null || git push origin main

# Get repo URL
REPO_URL=$(gh repo view --json url --jq '.url' 2>/dev/null || echo "unknown")

echo ""
echo "═══════════════════════════════════════════════════"
echo "  Done!"
echo "═══════════════════════════════════════════════════"
echo "  Repo: ${REPO_URL}"
echo ""
echo "  Next steps:"
echo "    1. Set up GCP: export GCP_PROJECT=your-project && bash infra/setup-gcp.sh"
echo "    2. Connect Cloud Build trigger to this repo for CI/CD"
echo ""
