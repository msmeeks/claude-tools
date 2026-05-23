#!/usr/bin/env bash
# Upload local images to the repo's pr-assets release and print markdown image lines.
#
# Usage: pr-image-upload.sh <PR_NUMBER> <image1> [image2 ...]
#        pr-image-upload.sh <image1> [image2 ...]   (no PR prefix)
#
# Requires: gh (GitHub CLI), authenticated to the target repo.
set -euo pipefail

RELEASE_TAG="pr-assets"

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)

if [[ -z "${REPO}" ]]; then
  echo "error: could not determine repo — run from inside the repository" >&2
  exit 1
fi

# If first arg looks like a PR number (all digits), use it as prefix
PR_PREFIX=""
if [[ $# -ge 1 && "$1" =~ ^[0-9]+$ ]]; then
  PR_PREFIX="pr${1}-"
  shift
fi

if [[ $# -eq 0 ]]; then
  echo "usage: $(basename "$0") [PR_NUMBER] <image1> [image2 ...]" >&2
  exit 1
fi

# Ensure the pr-assets release exists
if ! gh release view "$RELEASE_TAG" --repo "$REPO" >/dev/null 2>&1; then
  echo "Creating ${RELEASE_TAG} release..." >&2
  gh release create "$RELEASE_TAG" \
    --repo "$REPO" \
    --prerelease \
    --title "PR screenshot assets" \
    --notes "Asset bucket for PR screenshots — do not delete."
fi

TMPDIR_UPLOAD=$(mktemp -d)
trap 'rm -rf "$TMPDIR_UPLOAD"' EXIT

for IMG_PATH in "$@"; do
  if [[ ! -f "$IMG_PATH" ]]; then
    echo "error: file not found: $IMG_PATH" >&2
    exit 1
  fi

  BASENAME=$(basename "$IMG_PATH")
  UPLOAD_NAME="${PR_PREFIX}${BASENAME}"
  ALT="${BASENAME%.*}"

  # gh release upload uses the source filename as the download name,
  # so copy to a temp file with the desired upload name.
  UPLOAD_PATH="${TMPDIR_UPLOAD}/${UPLOAD_NAME}"
  cp "$IMG_PATH" "$UPLOAD_PATH"

  echo "Uploading ${UPLOAD_NAME}..." >&2
  gh release upload "$RELEASE_TAG" \
    --repo "$REPO" \
    "$UPLOAD_PATH" \
    --clobber

  echo "![${ALT}](https://github.com/${REPO}/releases/download/${RELEASE_TAG}/${UPLOAD_NAME})"
done
