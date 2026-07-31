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

OVERLAY_PARTS = [
    ("v1_overlay.part00", 6000, "488d1d3d3a758d96a6f1aace2188a53b8e263f3cb0c55be5a98e3ddfe5ed580f"),
    ("v1_overlay.part01", 6000, "f28b6af24e41ba58079fc0c1140a2bef868b178504ea957f7c47437ec7f62c0b"),
    ("v1_overlay.part02", 6000, "26c4977a6a30cc00e63a4eb5c1c42dbd4b99b517f919f5f0b8a22e354d9f08e9"),
    ("v1_overlay.part03", 6000, "199206e823e30bdd199a0ec0c5d5ee1306626559431abd0c0bd9c9e9de2f5f49"),
    ("v1_overlay.part04", 6000, "f98be83996c8e96125d37aa02088053880979ff6bf1d0ebb2f289ee850e426b3"),
    ("v1_overlay.part05", 6000, "7cda53c1b785975d1e72d0d084ef0b07a6c4f7858b902521bc4d138eccb4e277"),
    ("v1_overlay.part06", 6000, "a9d17d6d0f8cf3b74b843e9013685a399b5a030da4f452fd84f44e45051f7510"),
    ("v1_overlay.part07", 3908, "c77deb177c3d0cf55e1ddfacadb60635d58f16c934fba90172a37e3a2c734a78"),
]

overlay_chunks: list[str] = []
for name, expected_length, expected_sha in OVERLAY_PARTS:
    path = ROOT / "bundle" / name
    if not path.is_file():
        raise SystemExit(f"Missing v1 overlay part: {path}")
    chunk = "".join(path.read_text(encoding="ascii").split())
    actual_sha = hashlib.sha256(chunk.encode("ascii")).hexdigest()
    if len(chunk) != expected_length or actual_sha != expected_sha:
        raise SystemExit(
            f"Invalid {name}: length={len(chunk)} sha256={actual_sha}; "
            f"expected length={expected_length} sha256={expected_sha}"
        )
    overlay_chunks.append(chunk)

overlay_encoded = "".join(overlay_chunks)
overlay_payload = base64.b64decode(overlay_encoded, validate=True)
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
