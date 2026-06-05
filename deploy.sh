#!/usr/bin/env bash
# Usage:
#   ./deploy.sh            — keeps current version, updates timestamp + commit
#   ./deploy.sh v3.2.0     — bumps version
set -e

BRANCH="srockprofilebakmarch062026"
VERSION="${1:-}"

if [ -z "$VERSION" ]; then
  VERSION=$(grep -oP "version: '\K[^']+" docs/index.html | head -1)
fi

COMMIT=$(git rev-parse --short HEAD)
DEPLOYED_AT=$(date -u '+%Y-%m-%d %H:%M UTC')

# 1. Stamp BUILD in docs/index.html
sed -i "s|const BUILD = {[^}]*};|const BUILD = { version: '$VERSION', deployedAt: '$DEPLOYED_AT', commit: '$COMMIT' };|" docs/index.html

# 2. Bump service worker cache version so browsers drop old cache immediately
CURRENT_SW=$(grep -oP "msa-v\K\d+" docs/sw.js | head -1)
NEXT_SW=$((CURRENT_SW + 1))
sed -i "s/msa-v${CURRENT_SW}/msa-v${NEXT_SW}/g" docs/sw.js
echo "SW cache: msa-v${CURRENT_SW} → msa-v${NEXT_SW}"

# 3. Sync root copies (GitHub Pages works from root or /docs)
cp docs/index.html index.html
cp docs/sw.js sw.js
cp docs/manifest.json manifest.json 2>/dev/null || true
cp docs/icon.svg icon.svg 2>/dev/null || true

echo "Stamped: $VERSION · $DEPLOYED_AT · $COMMIT"

git add docs/index.html docs/sw.js index.html sw.js manifest.json icon.svg
git commit -m "deploy: $VERSION · $DEPLOYED_AT (SW cache msa-v${NEXT_SW})"

git push -u origin "$BRANCH"

echo ""
echo "✅ Live: $VERSION deployed at $DEPLOYED_AT"
echo "   SW cache busted to msa-v${NEXT_SW} — browsers will load fresh on next visit"
