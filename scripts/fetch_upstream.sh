#!/bin/sh
# Fetch the pinned openai/math commit as a light sparse checkout (no PDFs,
# no Lean library sources): enough to rebuild the atlas data.
# Usage: sh scripts/fetch_upstream.sh [--latest] [--lean-library] [target-dir]   (default: ../openai-math-upstream)
# --lean-library also fetches lean/OAI/ (about 1.7 GB) for scripts/build_lean_claims.py.
# --latest moves the pin in upstream.json to openai/math's current main first.
set -eu
here=$(cd "$(dirname "$0")/.." && pwd)
latest=0
library=0
while [ $# -gt 0 ]; do
  case "$1" in
    --latest) latest=1; shift ;;
    --lean-library) library=1; shift ;;
    *) break ;;
  esac
done
target=${1:-"$here/../openai-math-upstream"}
if [ "$latest" = 1 ]; then
  # Move the pin to openai/math's current main and record it in upstream.json.
  head=$(git ls-remote https://github.com/openai/math.git refs/heads/main | cut -f1)
  python3 - "$here/upstream.json" "$head" <<'PY'
import json, sys
p, head = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["commit"] = head
open(p, "w").write(json.dumps(d, indent=2) + "\n")
PY
fi
commit=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['commit'])" "$here/upstream.json")
if [ ! -d "$target/.git" ]; then
  git clone --filter=blob:none --no-checkout https://github.com/openai/math.git "$target"
fi
cd "$target"
git sparse-checkout init --no-cone
cat > .git/info/sparse-checkout <<'PATTERNS'
/*.md
/*.tex
/LICENSE
/lean/formalization.yaml
/lean/README.md
/lean/lean-toolchain
/lean/lakefile.lean
/lean/lake-manifest.json
/lean/docs/
/lean/ComparatorChallenges/
/preprints/
!*.pdf
!*.png
!*.jpg
!*.jpeg
!*.gif
!*.svg
!*.eps
!*.zip
!*.gz
!*.tar
PATTERNS
if [ "$library" = 1 ]; then
  # The whole Lean library (about 1.7 GB) for scripts/build_lean_claims.py.
  printf '%s\n' '/lean/OAI/' >> .git/info/sparse-checkout
fi
git fetch --quiet origin "$commit"
git checkout --quiet "$commit"
echo "openai/math at $(git rev-parse HEAD) in $target"
