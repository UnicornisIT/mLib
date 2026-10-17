"""Check that every release version source agrees, optionally against a release tag.

The tag does not have to exist: the release workflow creates it only when it publishes the Release.

Usage:
    python scripts/check_release.py                 # versions must match each other
    python scripts/check_release.py --tag v1.2.3    # ...and the tag, and release notes must exist
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TAG_PATTERN = re.compile(r"^v(?P<version>\d+\.\d+\.\d+(?:-[0-9A-Za-z.]+)?)$")
JSON_SOURCES = (
    "frontend/package.json",
    "desktop/package.json",
    "desktop/frontend-runtime/package.json",
)
DESKTOP_LOCKFILE = "desktop/package-lock.json"
BACKEND_CONFIG = "backend/app/core/config.py"


def read_versions() -> dict[str, str | None]:
    versions: dict[str, str | None] = {}
    for relative in JSON_SOURCES:
        versions[relative] = json.loads((ROOT / relative).read_text(encoding="utf-8")).get("version")
    lockfile = json.loads((ROOT / DESKTOP_LOCKFILE).read_text(encoding="utf-8"))
    versions[DESKTOP_LOCKFILE] = lockfile.get("version")
    versions[f"{DESKTOP_LOCKFILE} (packages[\"\"])"] = lockfile.get("packages", {}).get("", {}).get("version")
    match = re.search(
        r'^\s*app_version:\s*str\s*=\s*"([^"]+)"',
        (ROOT / BACKEND_CONFIG).read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    versions[BACKEND_CONFIG] = match.group(1) if match else None
    return versions


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", help="release tag, for example v0.0.4-alpha")
    args = parser.parse_args()

    errors: list[str] = []
    versions = read_versions()
    for source, version in versions.items():
        if not version:
            errors.append(f"{source}: version not found")
    distinct = {version for version in versions.values() if version}
    if len(distinct) > 1:
        details = "\n".join(f"  {source}: {version}" for source, version in versions.items())
        errors.append(f"version sources disagree:\n{details}")

    if args.tag:
        tag_match = TAG_PATTERN.match(args.tag)
        if not tag_match:
            errors.append(f"tag '{args.tag}' does not match vX.Y.Z[-suffix]")
        elif distinct and tag_match.group("version") not in distinct:
            errors.append(f"tag '{args.tag}' does not match version {', '.join(sorted(distinct))}")
        notes = ROOT / ".github" / "release-notes" / f"{args.tag}.md"
        if not notes.is_file():
            errors.append(f"release notes {notes.relative_to(ROOT).as_posix()} are missing")

    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    suffix = f" and tag {args.tag}" if args.tag else ""
    print(f"Release version {distinct.pop()} is consistent across {len(versions)} sources{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
