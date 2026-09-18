#!/usr/bin/env bash
# Download win_amd64 AND win32 wheels for ~100 popular packages with native
# extensions, one package at a time so a single unavailable wheel (win32
# support is increasingly rare) doesn't abort the whole batch.
set -uo pipefail
cd "$(dirname "$0")"
source ../.venv/Scripts/activate

mkdir -p pip_downloads_win_amd64 pip_downloads_win32
: > fetch_pip_wheels.log

fetch() {
  local platform="$1" dest="$2" pkg="$3"
  python -m pip download --dest "$dest" --platform "$platform" \
    --python-version 312 --implementation cp --abi cp312 \
    --only-binary=:all: --no-deps "$pkg" >> fetch_pip_wheels.log 2>&1
  if [ $? -eq 0 ]; then
    echo "OK   $platform $pkg"
  else
    echo "MISS $platform $pkg"
  fi
}

while IFS= read -r pkg; do
  [ -z "$pkg" ] && continue
  fetch win_amd64 pip_downloads_win_amd64 "$pkg"
  fetch win32 pip_downloads_win32 "$pkg"
done < pkg_list_pip.txt

echo "--- win_amd64 wheels: $(ls pip_downloads_win_amd64/*.whl 2>/dev/null | wc -l)"
echo "--- win32 wheels:     $(ls pip_downloads_win32/*.whl 2>/dev/null | wc -l)"
