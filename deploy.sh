#!/usr/bin/env bash
# Usage:
#   ./deploy.sh            — keeps current version, updates timestamp + commit
#   ./deploy.sh v3.1.0     — bumps version, updates timestamp + commit
set -e

BRANCH="srockprofilebakmarch062026"
VERSION="${1:-}"

# Read current version from index.html if none provided
if [ -z "$VERSION" ]; then
  VERSION=$(grep -oP "version: '\K[^']+" docs/index.html | head -1)
fi

COMMIT=$(git rev-parse --short HEAD)
DEPLOYED_AT=$(date -u '+%Y-%m-%d %H:%M UTC')

# Stamp the BUILD constant in index.html (single line, safe replacement)
sed -i "s|const BUILD = {[^}]*};|const BUILD = { version: '$VERSION', deployedAt: '$DEPLOYED_AT', commit: '$COMMIT' };|" docs/index.html

echo "Stamped: $VERSION · $DEPLOYED_AT · $COMMIT"

git add docs/index.html
git commit -m "deploy: $VERSION · $DEPLOYED_AT (commit: $COMMIT)"

# Push feature branch
CURRENT=$(git rev-parse --abbrev-ref HEAD)
git push -u origin "$CURRENT"

# Merge into GitHub Pages branch and push
git checkout "$BRANCH"
git merge "$CURRENT" --no-ff -m "merge: $VERSION deployed $DEPLOYED_AT"
git push -u origin "$BRANCH"
git checkout "$CURRENT"

echo ""
echo "Live on GitHub Pages: $VERSION deployed at $DEPLOYED_AT"
