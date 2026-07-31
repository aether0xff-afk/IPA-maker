#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMMIT="4f934274ad3dc35ae40f86da8c59d76a0a47c023"
REPOSITORY="https://github.com/liusichao/Hitomi-Downloader.git"
CACHE="$ROOT/.runtime-cache/hitomi-source-$COMMIT"
SOURCE="$CACHE/repository"
OUTPUT="$ROOT/Sources/AppModule/Resources/PythonApp/original_pyc.zip"

mkdir -p "$CACHE" "$(dirname "$OUTPUT")"

if [[ ! -d "$SOURCE/.git" ]]; then
  rm -rf "$SOURCE"
  git clone --filter=blob:none --no-checkout "$REPOSITORY" "$SOURCE"
fi

git -C "$SOURCE" fetch --depth 1 origin "$COMMIT"
git -C "$SOURCE" checkout --detach --force "$COMMIT"
ACTUAL_COMMIT="$(git -C "$SOURCE" rev-parse HEAD)"
if [[ "$ACTUAL_COMMIT" != "$COMMIT" ]]; then
  echo "Hitomi source commit mismatch: $ACTUAL_COMMIT" >&2
  exit 10
fi

python3 - "$SOURCE/src" "$OUTPUT" "$COMMIT" <<'PY'
from pathlib import Path
import hashlib
import json
import sys
import zipfile

source = Path(sys.argv[1])
output = Path(sys.argv[2])
commit = sys.argv[3]

if not (source / "extractor").is_dir():
    raise SystemExit("Pinned source snapshot has no src/extractor directory")

extensions = {".py", ".json", ".js", ".txt", ".hdl"}
files = sorted(
    path for path in source.rglob("*")
    if path.is_file() and path.suffix.lower() in extensions
)
extractors = [path for path in files if path.parent.name == "extractor" and path.name.endswith("_downloader.py")]
if len(extractors) < 75:
    raise SystemExit(f"Unexpectedly small extractor snapshot: {len(extractors)}")

metadata = {
    "sourceRepository": "liusichao/Hitomi-Downloader",
    "sourceCommit": commit,
    "extractorCount": len(extractors),
    "fileCount": len(files),
    "format": "Python source zip",
}

with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    # zipimport does not reliably discover an implicit namespace package.
    archive.writestr("extractor/__init__.py", "# Embedded Hitomi extractor package\n")
    for path in files:
        relative = path.relative_to(source).as_posix()
        if relative == "extractor/__init__.py":
            continue
        archive.write(path, relative)
    archive.writestr("HITOMI_PAYLOAD.json", json.dumps(metadata, ensure_ascii=False, indent=2))

with zipfile.ZipFile(output) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit(f"Corrupt payload member: {bad}")

print(f"Pinned Hitomi source commit: {commit}")
print(f"Embedded extractor modules: {len(extractors)}")
print(f"Embedded source files: {len(files)}")
print(f"Payload SHA-256: {hashlib.sha256(output.read_bytes()).hexdigest()}")
PY
