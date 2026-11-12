#!/usr/bin/env bash
# Push this repo's backend to its Hugging Face Space.
#
# A Space is its own git repo and expects Dockerfile + README.md at the root, so
# this assembles that layout in a temp directory rather than restructuring the
# GitHub repo around one deployment target.
#
#   ./deploy/huggingface/sync.sh <hf-username>/<space-name>
#
# Requires: `hf auth login` with a write-scoped token.
set -euo pipefail

SPACE="${1:?usage: sync.sh <owner>/<space-name>}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

echo "→ assembling $SPACE from $ROOT"
git clone --quiet "https://huggingface.co/spaces/$SPACE" "$STAGE/space"

cd "$STAGE/space"
# Replace tracked content wholesale so deletions upstream propagate too.
find . -mindepth 1 -maxdepth 1 -not -name '.git' -exec rm -rf {} +

cp "$ROOT/deploy/huggingface/Dockerfile" ./Dockerfile
cp "$ROOT/deploy/huggingface/README.md"  ./README.md
mkdir -p backend
# --exclude keeps local-only cruft (venvs, caches, .env) out of a public Space.
tar -C "$ROOT" \
    --exclude='__pycache__' --exclude='*.pyc' --exclude='.env' \
    --exclude='.venv*' --exclude='.pytest_cache' \
    -cf - backend | tar -C . -xf -

git add -A
if git diff --cached --quiet; then
  echo "→ no changes"
  exit 0
fi
git -c user.name="sync.sh" -c user.email="noreply@huggingface.co" \
    commit --quiet -m "Sync backend from GitHub"
git push --quiet origin HEAD:main
echo "→ pushed. Build: https://huggingface.co/spaces/$SPACE"
