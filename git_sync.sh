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
if ! git check-ref-format --allow-onelevel "$VERSION"; then
    echo "Error: APP_VERSION '$VERSION' is not a valid git tag name." >&2
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

HEAD_COMMIT=$(git rev-parse HEAD)
if git rev-parse -q --verify "refs/tags/$VERSION" >/dev/null; then
    TAG_COMMIT=$(git rev-list -n 1 "$VERSION")
    if [ "$TAG_COMMIT" != "$HEAD_COMMIT" ]; then
        echo "Error: tag $VERSION already exists on a different commit." >&2
        echo "       existing: $TAG_COMMIT" >&2
        echo "       current:  $HEAD_COMMIT" >&2
        exit 1
    fi
    echo "Tag $VERSION already exists on the current commit."
else
    git tag "$VERSION"
    echo "Created tag $VERSION."
fi

git push origin "$BRANCH"
git push origin "$VERSION"

echo "Git sync complete on branch ${BRANCH} with version/tag ${VERSION}."
