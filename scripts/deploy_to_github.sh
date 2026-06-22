#!/usr/bin/env bash
# Push this standalone tree to a dedicated GitHub repository.
set -euo pipefail

TARGET_REPO="${1:-Poyqraz/PyFoldable}"
BRANCH="${2:-main}"
REMOTE_URL="https://github.com/${TARGET_REPO}.git"

cd "$(git rev-parse --show-toplevel)"

pick_token() {
  local name value
  for name in GH_PAT GITHUB_PAT PYFOLDABLE_GITHUB_TOKEN GITHUB_TOKEN GH_TOKEN PAT; do
    value="${!name-}"
    if [[ -n "$value" && "$value" != ghs_* ]]; then
      printf '%s' "$value"
      return 0
    fi
  done
  return 1
}

if TOKEN="$(pick_token)"; then
  git remote set-url origin "https://x-access-token:${TOKEN}@github.com/${TARGET_REPO}.git"
else
  git remote set-url origin "$REMOTE_URL"
fi

git push -u origin "HEAD:refs/heads/${BRANCH}"
echo "ok: pushed to https://github.com/${TARGET_REPO} (${BRANCH})"
