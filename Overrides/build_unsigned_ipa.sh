#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUILD="$ROOT/build-unsigned"
DERIVED="$BUILD/DerivedData"
PROJECT="$ROOT/HitomiSwiftFull.xcodeproj"
APP="$DERIVED/Build/Products/Release-iphoneos/HitomiSwiftFull.app"
IPA="$BUILD/HitomiSwiftFull-unsigned.ipa"
PYTHON_ARCHIVE="$ROOT/Runtime/PythonFrameworks/Python.xcframework/ios-arm64/libPython3.8.a"

if ! command -v xcodebuild >/dev/null 2>&1; then
  echo "macOS와 Xcode가 필요합니다." >&2
  exit 2
fi
if ! command -v xcodegen >/dev/null 2>&1; then
  echo "xcodegen이 필요합니다: brew install xcodegen" >&2
  exit 3
fi

cd "$ROOT"

if [[ "${HITOMI_SKIP_RUNTIMES:-0}" != "1" ]]; then
  ./Scripts/fetch_hitomi_payload.sh
  ./Scripts/fetch_python38_runtime.sh
  ./Scripts/fetch_torrent_runtime.sh
fi

test -f "$PYTHON_ARCHIVE"
test -f "$ROOT/Sources/AppModule/Resources/PythonApp/original_pyc.zip"
test -d "$ROOT/Sources/AppModule/Resources/python"

python3 - "$ROOT/project.yml" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text = text.replace("\n        optional: true", "")
path.write_text(text, encoding="utf-8")
PY

rm -rf "$BUILD" "$PROJECT"
mkdir -p "$BUILD"
xcodegen generate --spec project.yml

PYTHON_LDFLAGS="-Wl,-force_load,$PYTHON_ARCHIVE -Wl,-export_dynamic -lz -lsqlite3"

xcodebuild \
  -project "$PROJECT" \
  -scheme HitomiSwiftFull \
  -configuration Release \
  -sdk iphoneos \
  -destination 'generic/platform=iOS' \
  -derivedDataPath "$DERIVED" \
  CODE_SIGNING_ALLOWED=NO \
  CODE_SIGNING_REQUIRED=NO \
  CODE_SIGN_IDENTITY='' \
  OTHER_LDFLAGS="$PYTHON_LDFLAGS" \
  build

test -d "$APP"

ditto "$ROOT/Sources/AppModule/Resources/PythonApp" "$APP/PythonApp"
ditto "$ROOT/Sources/AppModule/Resources/python" "$APP/python"

./Scripts/embed_runtime_frameworks.sh "$APP"

if ! nm -gU "$APP/HitomiSwiftFull" | grep -q '_Py_Initialize'; then
  echo "Py_Initialize is not exported from the app executable." >&2
  exit 20
fi

mkdir -p "$BUILD/Payload"
cp -R "$APP" "$BUILD/Payload/HitomiSwiftFull.app"
(
  cd "$BUILD"
  /usr/bin/zip -qry "$(basename "$IPA")" Payload
)

unzip -t "$IPA" >/dev/null
printf 'IPA: %s\n' "$IPA"
printf 'IPA SHA-256: '
shasum -a 256 "$IPA" | awk '{print $1}'
