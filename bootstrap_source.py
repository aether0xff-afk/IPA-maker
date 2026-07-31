#!/usr/bin/env python3
from __future__ import annotations

import base64
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
    archive.testzip()
    archive.extractall(ROOT)

# Xcode 16.4 ships Swift 6.1. The source package was authored with the 6.2
# manifest version, but it doesn't use manifest APIs that require 6.2.
package = ROOT / "Package.swift"
text = package.read_text(encoding="utf-8")
text = text.replace("// swift-tools-version: 6.2", "// swift-tools-version: 6.1", 1)
package.write_text(text, encoding="utf-8")

# Xcode's actor isolation checking requires the service itself to live on the
# main actor because the resolver protocol is main-actor isolated.
resolver = ROOT / "Sources/AppModule/Resolvers/ResolverService.swift"
text = resolver.read_text(encoding="utf-8")
text = text.replace(
    "final class ResolverService: @unchecked Sendable {",
    "@MainActor\nfinal class ResolverService: @unchecked Sendable {",
)
resolver.write_text(text, encoding="utf-8")

# The resources directory always exists in this repository build. Avoid using
# an XcodeGen key that differs between releases.
project = ROOT / "project.yml"
text = project.read_text(encoding="utf-8")
text = text.replace("\n        optional: true", "")
project.write_text(text, encoding="utf-8")

for script in (ROOT / "Scripts").glob("*.sh"):
    script.chmod(0o755)

print(f"Restored {len(payload):,} bytes of source into {ROOT}")
