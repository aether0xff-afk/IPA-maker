#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
import plistlib
import zipfile

ROOT = Path(__file__).resolve().parent
BUNDLE = ROOT / "bundle"
PARTS = [BUNDLE / f"original_source_overlay.chunk{i:02d}" for i in range(22)]
EXPECTED_ENCODED_SIZE = 218_808
EXPECTED_SIZE = 164_106
EXPECTED_SHA256 = "222b88369bc2e1786933be8ff5798fa103695aee2a904bc893494f1cf7b7d904"
EXPECTED_SOURCE_SHA256 = "69a04581949a04d4a8af1cdec20254eb53708af925ce53edc69fde57e1a535f6"
EXPECTED_SOURCE_COMMIT = "6a87311"
EXPECTED_SOURCE_EXTRACTORS = 75
EXPECTED_FALLBACK_EXTRACTORS = 9
EXPECTED_ROUTABLE_EXTRACTORS = 84

missing = [str(path) for path in PARTS if not path.is_file()]
if missing:
    raise SystemExit(f"Missing original-source overlay chunks: {missing}")

encoded = "".join("".join(path.read_text(encoding="ascii").split()) for path in PARTS)
if len(encoded) != EXPECTED_ENCODED_SIZE:
    raise SystemExit(f"Encoded overlay size mismatch: {len(encoded)} != {EXPECTED_ENCODED_SIZE}")
payload = base64.b64decode(encoded, validate=True)
digest = hashlib.sha256(payload).hexdigest()
if len(payload) != EXPECTED_SIZE or digest != EXPECTED_SHA256:
    raise SystemExit(
        f"Original-source overlay mismatch: size={len(payload)}, sha256={digest}; "
        f"expected size={EXPECTED_SIZE}, sha256={EXPECTED_SHA256}"
    )

with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit(f"Corrupt original-source overlay member: {bad}")
    archive.extractall(ROOT)

python_app = ROOT / "Sources/AppModule/Resources/PythonApp"
source_zip = python_app / "original_source.zip"
source_digest = hashlib.sha256(source_zip.read_bytes()).hexdigest()
if source_digest != EXPECTED_SOURCE_SHA256:
    raise SystemExit(
        f"Original source ZIP mismatch: {source_digest} != {EXPECTED_SOURCE_SHA256}"
    )

manifest = json.loads((python_app / "legacy_manifest.json").read_text(encoding="utf-8"))
checks = {
    "sourceCommit": EXPECTED_SOURCE_COMMIT,
    "sourceExtractorCount": EXPECTED_SOURCE_EXTRACTORS,
    "legacyFallbackCount": EXPECTED_FALLBACK_EXTRACTORS,
    "extractorCount": EXPECTED_ROUTABLE_EXTRACTORS,
}
for key, expected in checks.items():
    if manifest.get(key) != expected:
        raise SystemExit(f"Unexpected {key}: {manifest.get(key)!r} != {expected!r}")
if len(manifest.get("entries", [])) != EXPECTED_ROUTABLE_EXTRACTORS:
    raise SystemExit("Unexpected manifest entry count")

with zipfile.ZipFile(source_zip) as source:
    members = [
        name for name in source.namelist()
        if name.startswith("extractor/") and name.endswith("_downloader.py")
    ]
    if len(members) != EXPECTED_SOURCE_EXTRACTORS:
        raise SystemExit(f"Unexpected source member count: {len(members)}")

info_path = ROOT / "Info.plist"
with info_path.open("rb") as stream:
    info = plistlib.load(stream)
info["CFBundleShortVersionString"] = "1.0.1"
info["CFBundleVersion"] = "101"
with info_path.open("wb") as stream:
    plistlib.dump(info, stream, fmt=plistlib.FMT_XML, sort_keys=False)

for script in (ROOT / "Scripts").glob("*.sh"):
    script.chmod(0o755)

print(f"Applied original-source rebuild overlay: {len(payload):,} bytes, SHA-256 {digest}")
print(
    f"Pinned routing: {EXPECTED_SOURCE_EXTRACTORS} original source + "
    f"{EXPECTED_FALLBACK_EXTRACTORS} Python 3.8 fallback = "
    f"{EXPECTED_ROUTABLE_EXTRACTORS} extractors"
)
print(f"Original source ZIP SHA-256: {source_digest}")
