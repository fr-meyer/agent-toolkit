#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$skill_dir/SKILL.md" <<'PY'
from pathlib import Path
import sys

text = Path(sys.argv[1]).read_text(encoding="utf-8")
rollback = text.index("### 2.5 Capture or Verify the Rollback Image")
build = text.index("### 2.6 Build and Verify the Candidate")
classification = text.index("### 3. Classify the State")
if not rollback < build < classification:
    raise SystemExit("candidate build must follow verified rollback preservation")

recipe = text[build:classification]
if "docker compose build --quiet" in recipe:
    raise SystemExit("quiet Compose build output is not an image-ID source")
required = (
    "jq -er",
    'select(type == "string" and length > 0)',
    "docker compose build <service>",
    "docker image inspect --format '{{.Id}}'",
    'docker run --rm --entrypoint sh "$CANDIDATE_IMAGE_ID"',
    "docker compose up -d --no-build <service>",
)
for marker in required:
    if marker not in recipe:
        raise SystemExit(f"candidate recipe is missing: {marker}")
if not (
    recipe.index("CANDIDATE_IMAGE=")
    < recipe.index("docker compose build <service>")
    < recipe.index("CANDIDATE_IMAGE_ID=")
    < recipe.index('docker run --rm --entrypoint sh "$CANDIDATE_IMAGE_ID"')
    < recipe.index("docker compose up -d --no-build <service>")
):
    raise SystemExit("candidate recipe ordering is unsafe")
print("candidate image recipe: ok")
PY
