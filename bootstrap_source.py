#!/usr/bin/env python3
from __future__ import annotations

import base64
import hashlib
import io
from pathlib import Path
import plistlib
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

# Sideloading tools need the standard application bundle keys even though
# Xcode can compile a custom plist without them.
info_plist = ROOT / "Info.plist"
with info_plist.open("rb") as stream:
    info = plistlib.load(stream)
info.update(
    {
        "CFBundleDevelopmentRegion": "$(DEVELOPMENT_LANGUAGE)",
        "CFBundleDisplayName": "Hitomi Swift Full",
        "CFBundleExecutable": "$(EXECUTABLE_NAME)",
        "CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "$(PRODUCT_NAME)",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "1.0.0",
        "CFBundleVersion": "100",
        "LSRequiresIPhoneOS": True,
        "LSSupportsOpeningDocumentsInPlace": True,
        "UILaunchScreen": {},
        "UISupportedInterfaceOrientations": [
            "UIInterfaceOrientationPortrait",
            "UIInterfaceOrientationLandscapeLeft",
            "UIInterfaceOrientationLandscapeRight",
        ],
        "UISupportedInterfaceOrientations~ipad": [
            "UIInterfaceOrientationPortrait",
            "UIInterfaceOrientationPortraitUpsideDown",
            "UIInterfaceOrientationLandscapeLeft",
            "UIInterfaceOrientationLandscapeRight",
        ],
    }
)
with info_plist.open("wb") as stream:
    plistlib.dump(info, stream, fmt=plistlib.FMT_XML, sort_keys=False)

for script in (ROOT / "Scripts").glob("*.sh"):
    script.chmod(0o755)

print(f"Restored base source: {len(payload):,} bytes")
print(f"Applied v1.0 overlay: {len(overlay_payload):,} bytes ({overlay_sha})")
