#!/usr/bin/env bash
set -euo pipefail

tracked="$(git ls-files -- out data/snapshots)"
if [[ -n "${tracked}" ]]; then
  echo "Tracked runtime artifacts are not allowed under out/ or data/snapshots/."
  echo "Remove these from git tracking:"
  printf '%s\n' "${tracked}"
  exit 1
fi

echo "Runtime artifact tracking policy OK."
