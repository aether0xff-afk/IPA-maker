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
BUNDLE = ROOT / 'bundle'
PARTS = [BUNDLE / f'original_source_overlay.chunk{i:02d}' for i in range(22)]
EXPECTED_ENCODED_SIZE = 217_492
EXPECTED_SIZE = 163_119
EXPECTED_SHA256 = 'ed8731be2e5ddcb962f3d7d4860ee3f793537fe161b4a79733c5c3168c46a5b3'
EXPECTED_SOURCE_SHA256 = '69a04581949a04d4a8af1cdec20254eb53708af925ce53edc69fde57e1a535f6'
EXPECTED_SOURCE_COMMIT = '6a87311'
EXPECTED_EXTRACTORS = 75

missing = [str(path) for path in PARTS if not path.is_file()]
if missing:
    raise SystemExit(f'Missing original-source overlay chunks: {missing}')

encoded = ''.join(''.join(path.read_text(encoding='ascii').split()) for path in PARTS)
if len(encoded) != EXPECTED_ENCODED_SIZE:
    raise SystemExit(f'Encoded overlay size mismatch: {len(encoded)} != {EXPECTED_ENCODED_SIZE}')
payload = base64.b64decode(encoded, validate=True)
digest = hashlib.sha256(payload).hexdigest()
if len(payload) != EXPECTED_SIZE or digest != EXPECTED_SHA256:
    raise SystemExit(
        f'Original-source overlay mismatch: size={len(payload)}, sha256={digest}; '
        f'expected size={EXPECTED_SIZE}, sha256={EXPECTED_SHA256}'
    )

with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit(f'Corrupt original-source overlay member: {bad}')
    archive.extractall(ROOT)

python_app = ROOT / 'Sources/AppModule/Resources/PythonApp'
source_zip = python_app / 'original_source.zip'
source_digest = hashlib.sha256(source_zip.read_bytes()).hexdigest()
if source_digest != EXPECTED_SOURCE_SHA256:
    raise SystemExit(
        f'Original source ZIP mismatch: {source_digest} != {EXPECTED_SOURCE_SHA256}'
    )

manifest = json.loads((python_app / 'legacy_manifest.json').read_text(encoding='utf-8'))
if manifest.get('sourceCommit') != EXPECTED_SOURCE_COMMIT:
    raise SystemExit(f"Unexpected source commit: {manifest.get('sourceCommit')!r}")
if manifest.get('extractorCount') != EXPECTED_EXTRACTORS:
    raise SystemExit(f"Unexpected extractor count: {manifest.get('extractorCount')!r}")

info_path = ROOT / 'Info.plist'
with info_path.open('rb') as stream:
    info = plistlib.load(stream)
info['CFBundleShortVersionString'] = '1.0.1'
info['CFBundleVersion'] = '101'
with info_path.open('wb') as stream:
    plistlib.dump(info, stream, fmt=plistlib.FMT_XML, sort_keys=False)

for script in (ROOT / 'Scripts').glob('*.sh'):
    script.chmod(0o755)

print(f'Applied original-source rebuild overlay: {len(payload):,} bytes, SHA-256 {digest}')
print(f'Pinned original extractor source: commit {EXPECTED_SOURCE_COMMIT}, {EXPECTED_EXTRACTORS} modules')
print(f'Original source ZIP SHA-256: {source_digest}')
