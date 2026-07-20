#!/usr/bin/env python3
"""Validate the safety and portability contract of the Linux release tarball."""
from __future__ import annotations

import argparse
import json
import sys
import tarfile
from pathlib import Path, PurePosixPath
from typing import Any

EXPECTED_ROOT = "citeseal_server-linux-x64"
REQUIRED_EXECUTABLES = {
    f"{EXPECTED_ROOT}/bin/citeseal_server",
    f"{EXPECTED_ROOT}/bin/run.sh",
}
MAX_MEMBERS = 10_000
MAX_UNPACKED_BYTES = 512 * 1024 * 1024


def _safe_member_path(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe path in tarball: {name!r}")
    if not path.parts or path.parts[0] != EXPECTED_ROOT:
        raise ValueError(f"unsafe path outside {EXPECTED_ROOT}: {name!r}")
    return path


def verify_tarball(path: str | Path) -> dict[str, Any]:
    """Validate *path* without extracting it and return a compact summary."""
    archive_path = Path(path)
    if not archive_path.is_file():
        raise ValueError(f"tarball not found: {archive_path}")

    seen: set[str] = set()
    files: set[str] = set()
    unpacked_bytes = 0

    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            members = archive.getmembers()
    except (OSError, tarfile.TarError) as exc:
        raise ValueError(f"invalid gzip tarball: {exc}") from exc

    if not members:
        raise ValueError("tarball is empty")
    if len(members) > MAX_MEMBERS:
        raise ValueError(f"tarball has too many members: {len(members)}")

    for member in members:
        _safe_member_path(member.name)
        if member.name in seen:
            raise ValueError(f"duplicate tarball member: {member.name!r}")
        seen.add(member.name)

        if member.issym() or member.islnk():
            raise ValueError(
                "links are not allowed in portable tarballs: "
                f"{member.name!r} -> {member.linkname!r}"
            )
        if not (member.isfile() or member.isdir()):
            raise ValueError(f"special file is not allowed: {member.name!r}")

        if member.isfile():
            files.add(member.name)
            unpacked_bytes += member.size
            if unpacked_bytes > MAX_UNPACKED_BYTES:
                raise ValueError("tarball exceeds the unpacked-size limit")

    missing = REQUIRED_EXECUTABLES - files
    if missing:
        raise ValueError(f"required release files missing: {sorted(missing)!r}")

    non_executable = [
        name
        for name in sorted(REQUIRED_EXECUTABLES)
        if next(member for member in members if member.name == name).mode & 0o111 == 0
    ]
    if non_executable:
        raise ValueError(f"release files are not executable: {non_executable!r}")

    return {
        "archive": str(archive_path),
        "members": len(members),
        "files": len(files),
        "links": 0,
        "unpacked_bytes": unpacked_bytes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tarball", type=Path)
    args = parser.parse_args(argv)
    try:
        summary = verify_tarball(args.tarball)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
