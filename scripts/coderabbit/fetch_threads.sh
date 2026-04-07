#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: ${0##*/} --repo-path <path> --repo-name <owner/repo> --pr-number <number> --out-dir <path>" >&2
}

REPO_PATH=""
REPO_NAME=""
PR_NUMBER=""
OUT_DIR=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo-path)
      REPO_PATH=${2:-}
      shift 2
      ;;
    --repo-name)
      REPO_NAME=${2:-}
      shift 2
      ;;
    --pr-number)
      PR_NUMBER=${2:-}
      shift 2
      ;;
    --out-dir)
      OUT_DIR=${2:-}
      shift 2
      ;;
    *)
      usage
      exit 1
      ;;
  esac
done

if [ -z "$REPO_PATH" ] || [ -z "$REPO_NAME" ] || [ -z "$PR_NUMBER" ] || [ -z "$OUT_DIR" ]; then
  usage
  exit 1
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "ERROR: gh CLI is required but was not found in PATH." >&2
  exit 1
fi

OWNER=${REPO_NAME%%/*}
NAME=${REPO_NAME#*/}
if [ -z "$OWNER" ] || [ -z "$NAME" ] || [ "$OWNER" = "$REPO_NAME" ]; then
  echo "ERROR: --repo-name must look like owner/repo" >&2
  exit 1
fi

RAW_DIR="$OUT_DIR/raw"
PAGES_DIR="$RAW_DIR/review-thread-pages"
mkdir -p "$PAGES_DIR"

QUERY=$(cat <<'GRAPHQL'
query($owner: String!, $name: String!, $number: Int!, $after: String) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      number
      title
      url
      headRefName
      headRefOid
      baseRefName
      reviewThreads(first: 100, after: $after) {
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          startLine
          originalStartLine
          comments(first: 100) {
            nodes {
              id
              url
              body
              createdAt
              author {
                login
              }
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
GRAPHQL
)

AFTER=""
PAGE=1
while true; do
  PAGE_FILE="$PAGES_DIR/review-threads-page-$(printf '%03d' "$PAGE").json"

  if [ -n "$AFTER" ]; then
    gh api graphql \
      -F owner="$OWNER" \
      -F name="$NAME" \
      -F number="$PR_NUMBER" \
      -F after="$AFTER" \
      -f query="$QUERY" \
      > "$PAGE_FILE"
  else
    gh api graphql \
      -F owner="$OWNER" \
      -F name="$NAME" \
      -F number="$PR_NUMBER" \
      -f query="$QUERY" \
      > "$PAGE_FILE"
  fi

  mapfile -t PAGE_META < <(python - "$PAGE_FILE" <<'PY'
import json
import sys

with open(sys.argv[1], 'r', encoding='utf-8') as f:
    data = json.load(f)

pr = (((data.get('data') or {}).get('repository') or {}).get('pullRequest'))
if pr is None:
    raise SystemExit('GraphQL response did not include repository.pullRequest')

page_info = ((pr.get('reviewThreads') or {}).get('pageInfo') or {})
print('true' if page_info.get('hasNextPage') else 'false')
print(page_info.get('endCursor') or '')
PY
  )

  HAS_NEXT=${PAGE_META[0]:-false}
  AFTER=${PAGE_META[1]:-}

  if [ "$HAS_NEXT" != "true" ] || [ -z "$AFTER" ]; then
    break
  fi

  PAGE=$((PAGE + 1))
done

python - "$PAGES_DIR" "$REPO_NAME" "$PR_NUMBER" "$REPO_PATH" "$RAW_DIR/raw-review-threads.json" "$OUT_DIR/raw-fetch-summary.json" <<'PY'
import glob
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

pages_dir = Path(sys.argv[1])
repo_name = sys.argv[2]
pr_number = int(sys.argv[3])
repo_path = sys.argv[4]
out_path = Path(sys.argv[5])
summary_path = Path(sys.argv[6])

page_files = sorted(glob.glob(str(pages_dir / 'review-threads-page-*.json')))
if not page_files:
    raise SystemExit('No review-thread pages were fetched.')

pull_request = None
threads = []
for path in page_files:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    pr = (((data.get('data') or {}).get('repository') or {}).get('pullRequest'))
    if pr is None:
        raise SystemExit(f'Missing pullRequest payload in {path}')
    if pull_request is None:
        pull_request = {
            'number': pr.get('number'),
            'title': pr.get('title'),
            'url': pr.get('url'),
            'headRefName': pr.get('headRefName'),
            'headRefOid': pr.get('headRefOid'),
            'baseRefName': pr.get('baseRefName'),
        }
    threads.extend((pr.get('reviewThreads') or {}).get('nodes') or [])

combined = {
    'repository': repo_name,
    'repoPath': repo_path,
    'pullRequest': pull_request,
    'reviewThreads': threads,
    'metadata': {
        'source': 'github-graphql-review-thread-fetch',
        'createdAt': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        'fetchedPages': len(page_files),
        'totalThreads': len(threads),
        'requestedPrNumber': pr_number,
    },
}

out_path.write_text(json.dumps(combined, indent=2) + '\n', encoding='utf-8')

summary = {
    'status': 'ok',
    'repository': repo_name,
    'repoPath': repo_path,
    'prNumber': pr_number,
    'fetchedPages': len(page_files),
    'totalThreads': len(threads),
    'rawPath': str(out_path),
}
summary_path.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
PY

echo "Fetched raw PR review-thread data into $RAW_DIR"
