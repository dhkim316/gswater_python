#!/bin/sh

set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$ROOT_DIR"

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Error: not inside a git repository." >&2
    exit 1
fi

VERSION=$(sed -n 's/^APP_VERSION = "\(.*\)"/\1/p' app.py | head -n 1)
if [ -z "$VERSION" ]; then
    echo "Error: APP_VERSION not found in app.py" >&2
    exit 1
fi

BRANCH=$(git branch --show-current)
if [ -z "$BRANCH" ]; then
    echo "Error: could not determine current branch." >&2
    exit 1
fi

COMMIT_MESSAGE="sync: ${VERSION}"
if [ "${1:-}" != "" ]; then
    COMMIT_MESSAGE="${COMMIT_MESSAGE} - $1"
fi

git add -A

if git diff --cached --quiet; then
    echo "No local changes to commit."
else
    git commit -m "$COMMIT_MESSAGE"
fi

git pull --rebase origin "$BRANCH"
git push origin "$BRANCH"

echo "Git sync complete on branch ${BRANCH} with version ${VERSION}."
