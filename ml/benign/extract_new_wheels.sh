#!/usr/bin/env bash
# Unzip pip_downloads_win_amd64/*.whl and pip_downloads_win32/*.whl into
# extracted/, one folder per (platform, package) pair so same-named
# packages from the two platforms don't collide/overwrite each other and
# so build_benign_features.py's per-package grouping still works.
set -uo pipefail
cd "$(dirname "$0")"

for tag in win_amd64 win32; do
  src="pip_downloads_${tag}"
  [ -d "$src" ] || continue
  for whl in "$src"/*.whl; do
    [ -e "$whl" ] || continue
    pkg=$(basename "$whl" | sed -E 's/-[0-9].*//')
    dest="extracted/pip_${tag}_${pkg}"
    [ -d "$dest" ] && continue
    mkdir -p "$dest"
    unzip -oq "$whl" -d "$dest"
  done
done

echo "extracted package folders: $(ls -d extracted/*/ | wc -l)"
