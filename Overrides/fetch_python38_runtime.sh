#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CACHE="$ROOT/.runtime-cache/python38"
ARCHIVE="$CACHE/python38-ios-support.tar.gz"
EXTRACT="$CACHE/extracted"
mkdir -p "$CACHE"

if [[ ! -f "$ARCHIVE" ]]; then
  echo "Searching official BeeWare Python 3.8 iOS support releases..."
  gh api --paginate --slurp repos/beeware/Python-Apple-support/releases > "$CACHE/releases.json"

  if python3 - "$CACHE/releases.json" "$CACHE/asset.json" <<'PY'
import json, sys
pages = json.load(open(sys.argv[1]))
releases = []
for page in pages:
    releases.extend(page if isinstance(page, list) else [])
for release in releases:
    for asset in release.get("assets", []):
        original = asset.get("name", "")
        name = original.lower()
        if "3.8" in name and "ios" in name and name.endswith(".tar.gz"):
            json.dump(
                {"name": original, "tag": release.get("tag_name")},
                open(sys.argv[2], "w"),
            )
            print(f"{release.get('tag_name')} / {original}")
            raise SystemExit(0)
raise SystemExit(2)
PY
  then
    ASSET_NAME="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["name"])' "$CACHE/asset.json")"
    RELEASE_TAG="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["tag"])' "$CACHE/asset.json")"
    rm -f "$ARCHIVE"
    gh release download "$RELEASE_TAG" \
      --repo beeware/Python-Apple-support \
      --pattern "$ASSET_NAME" \
      --output "$ARCHIVE"
    tar -tzf "$ARCHIVE" >/dev/null
  else
    echo "No prebuilt Python 3.8 support asset found; building the 3.8 branch."
    SRC="$CACHE/Python-Apple-support"
    rm -rf "$SRC"
    git clone --depth 1 --branch 3.8 https://github.com/beeware/Python-Apple-support.git "$SRC"
    make -C "$SRC" iOS
    BUILT="$(find "$SRC/dist" -type f -name '*iOS*.tar.gz' -print -quit)"
    if [[ -z "$BUILT" ]]; then
      echo "Python 3.8 iOS support build did not produce an archive." >&2
      find "$SRC/dist" -maxdepth 2 -type f -print || true
      exit 3
    fi
    cp "$BUILT" "$ARCHIVE"
    tar -tzf "$ARCHIVE" >/dev/null
  fi
fi

rm -rf "$EXTRACT" "$ROOT/Runtime/PythonFrameworks" "$ROOT/Sources/AppModule/Resources/python"
mkdir -p "$EXTRACT" "$ROOT/Runtime/PythonFrameworks" "$ROOT/Sources/AppModule/Resources/python"
tar -xzf "$ARCHIVE" -C "$EXTRACT"

while IFS= read -r -d '' framework; do
  cp -R "$framework" "$ROOT/Runtime/PythonFrameworks/"
done < <(find "$EXTRACT" -type d -name '*.xcframework' -print0)

PYHOME="$(find "$EXTRACT" -type d -path '*/lib/python3.8' -print -quit)"
if [[ -z "$PYHOME" ]]; then
  echo "Python 3.8 standard library not found in support archive" >&2
  find "$EXTRACT" -maxdepth 7 -type d | head -200
  exit 4
fi
mkdir -p "$ROOT/Sources/AppModule/Resources/python/lib"
cp -R "$PYHOME" "$ROOT/Sources/AppModule/Resources/python/lib/python3.8"

PLATFORM_CONFIG="$(find "$EXTRACT" -type d -name platform-config -print -quit || true)"
if [[ -n "$PLATFORM_CONFIG" ]]; then
  cp -R "$PLATFORM_CONFIG" "$ROOT/Sources/AppModule/Resources/python/"
fi

FRAMEWORK_COUNT="$(find "$ROOT/Runtime/PythonFrameworks" -maxdepth 1 -name '*.xcframework' | wc -l | tr -d ' ')"
if [[ "$FRAMEWORK_COUNT" == 0 ]]; then
  echo "No Python XCFrameworks were found." >&2
  exit 5
fi

echo "Python frameworks: $FRAMEWORK_COUNT"
echo "Python stdlib: $PYHOME"
