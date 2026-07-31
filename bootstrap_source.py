#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
PARTS = [
    ROOT / "bundle/source_bundle.part00",
    ROOT / "bundle/source_bundle.part01",
    ROOT / "bundle/source_bundle.rem00",
    ROOT / "bundle/source_bundle.rem01",
    ROOT / "bundle/source_bundle.rem02",
    ROOT / "bundle/source_bundle.rem03",
]

missing = [str(path) for path in PARTS if not path.is_file()]
if missing:
    raise SystemExit(f"Missing bundle parts: {missing}")

encoded = "".join(path.read_text(encoding="ascii") for path in PARTS)
payload = base64.b64decode(encoded, validate=True)
with zipfile.ZipFile(io.BytesIO(payload)) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit(f"Corrupt base source member: {bad}")
    archive.extractall(ROOT)

# The v1.0 overlay contains the full-runtime implementation while retaining
# the already verified v0.x source bundle as the compact repository base.
overlay_path = ROOT / "bundle/v1_overlay.b64"
overlay_encoded = "".join(overlay_path.read_text(encoding="ascii").split())
overlay_payload = base64.b64decode(overlay_encoded)
overlay_sha = hashlib.sha256(overlay_payload).hexdigest()
expected_overlay_sha = "3b880271e8e80e4d205258cbe2b638758723c01972e803ef1799c9a825a0b7f1"
if overlay_sha != expected_overlay_sha:
    raise SystemExit(
        f"v1 overlay SHA-256 mismatch: expected {expected_overlay_sha}, got {overlay_sha}"
    )
with zipfile.ZipFile(io.BytesIO(overlay_payload)) as archive:
    bad = archive.testzip()
    if bad:
        raise SystemExit(f"Corrupt v1 overlay member: {bad}")
    archive.extractall(ROOT)

for script in (ROOT / "Scripts").glob("*.sh"):
    script.chmod(0o755)

print(f"Restored base source: {len(payload):,} bytes")
print(f"Applied v1.0 overlay: {len(overlay_payload):,} bytes ({overlay_sha})")
