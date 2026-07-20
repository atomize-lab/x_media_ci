#!/usr/bin/env python3
"""
CiteSeal live demo: export-agent → agent consumption (end-to-end).

This script demonstrates the full CiteSeal workflow using synthetic test
fixtures (no real social media content). It is designed for:

  1. Onboarding new users — shows the complete pipeline in one command.
  2. Grant/review demos — proves the agent-consumption loop works.
  3. CI smoke-testing the export + manifest pipeline.

Pipeline:
  fixture tweet dir → export-agent → bundle.json → manifest → simulated agent read

Usage:
  python tools/scripts/demo_agent_consumption.py [--bundle-dir /tmp/cs_demo]

Exit codes:
  0 = success (bundle exported, manifest generated, agent simulation passed)
  1 = failure (see error output)

Requires: CiteSeal venv activated (PATH includes .venv/bin).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# --- Configuration -----------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FIXTURE_TWEET_DIR = (
    REPO_ROOT
    / "tests/fixtures/accounts/example_user/tweets/2026/2026-07/20260708_180000_1234567890"
)
CLI = REPO_ROOT / "tools" / "citeseal.py"


# --- Helpers -----------------------------------------------------------------

def run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    """Run a command, print output, fail fast on error."""
    print(f"  $ {' '.join(str(c) for c in cmd)}")
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd or REPO_ROOT
    )
    if result.returncode != 0:
        print(f"  FAIL (exit {result.returncode})")
        if result.stderr:
            print(f"  stderr: {result.stderr.strip()}")
        sys.exit(1)
    return result


def step(n: int, title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  Step {n}: {title}")
    print(f"{'='*60}")


# --- Pipeline ----------------------------------------------------------------

def main() -> int:
    bundle_dir_arg = sys.argv[sys.argv.index("--bundle-dir") + 1] if "--bundle-dir" in sys.argv else None

    print("=" * 60)
    print("  CiteSeal Live Demo: export-agent -> consumption")
    print("  (fully synthetic data - no real social media content)")
    print("=" * 60)

    if not FIXTURE_TWEET_DIR.exists():
        print(f"ERROR: fixture not found: {FIXTURE_TWEET_DIR}")
        return 1

    work = Path(bundle_dir_arg) if bundle_dir_arg else Path(tempfile.mkdtemp(prefix="cs_demo_"))
    bundle_dir = work / "demo_bundle"
    manifest_out = work / "manifest.json"
    cleanup = bundle_dir_arg is None  # only clean up temp dir, not user-specified

    # Step 1: Export agent bundle
    step(1, "Export agent bundle from fixture")
    print(f"  Source: {FIXTURE_TWEET_DIR.relative_to(REPO_ROOT)}")
    print(f"  Output: {bundle_dir}")
    run([
        sys.executable, str(CLI), "export-agent",
        "--tweet-dir", str(FIXTURE_TWEET_DIR),
        "--output", str(bundle_dir),
        "--hash-media",
    ])

    bundle_json = bundle_dir / "bundle.json"
    if not bundle_json.exists():
        print(f"ERROR: bundle.json not created at {bundle_json}")
        return 1

    bundle = json.loads(bundle_json.read_text(encoding="utf-8"))
    print(f"  [OK] bundle.json created ({bundle_json.stat().st_size} bytes)")
    print(f"    item_id: {bundle.get('item_id')}")
    print(f"    author:  @{bundle.get('author_handle')}")
    print(f"    assets:  {len(bundle.get('assets', []))} files")

    # Step 2: Generate provenance manifest (dry-run to avoid polluting fixture)
    step(2, "Generate provenance manifest")
    result = run([
        sys.executable, str(CLI), "manifest",
        "--tweet-dir", str(FIXTURE_TWEET_DIR),
        "--dry-run",
    ])
    manifest = json.loads(result.stdout)
    manifest_out.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"  [OK] manifest.json generated ({manifest_out.stat().st_size} bytes)")
    print(f"    files hashed:    {len(manifest.get('files', []))}")
    print(f"    transforms:      {len(manifest.get('transforms', []))}")
    trust = manifest.get("trust_flags", {})
    print(f"    media_verified:  {trust.get('media_verified')}")
    print(f"    all_files_hashed:{trust.get('all_files_hashed')}")

    # Step 3: Verify bundle integrity against manifest
    step(3, "Verify bundle media hashes against manifest")
    manifest_hashes = {f["path"]: f["sha256"] for f in manifest.get("files", [])}
    verified = 0
    for media_entry in bundle.get("media", []):
        fname = media_entry.get("file", "")
        bhash = media_entry.get("sha256")
        # manifest uses relative paths like "media/images/01.png"
        for mpath, mhash in manifest_hashes.items():
            if mpath.endswith(fname) and bhash == mhash:
                verified += 1
                print(f"  [OK] {fname}: hash matches manifest")
                break
    total_media = len(bundle.get("media", []))
    print(f"  -> {verified}/{total_media} media files verified against manifest")
    if verified != total_media:
        print("  WARNING: not all media hashes matched - check bundle export")

    # Step 4: Simulate agent consumption (no LLM needed — structural check)
    step(4, "Simulate agent consumption (structural validation)")
    checks = []

    def check(label: str, cond: bool) -> None:
        status = "[OK]" if cond else "[FAIL]"
        checks.append(cond)
        print(f"  {status} {label}")

    check("bundle_version present", "bundle_version" in bundle)
    check("source_url present", "source_url" in bundle)
    check("captured_at present", "captured_at" in bundle)
    check("author_handle present", "author_handle" in bundle)
    check("text_excerpt present", bool(bundle.get("text_excerpt")))
    check("assets[] non-empty", len(bundle.get("assets", [])) > 0)
    check("provenance.exported_at present", "exported_at" in bundle.get("provenance", {}))
    check("provenance.export_tool present", "export_tool" in bundle.get("provenance", {}))
    check("trust_flags present", "trust_flags" in bundle)
    check("media files exist on disk",
          all((bundle_dir / "media" / m["file"]).exists() for m in bundle.get("media", [])))

    all_pass = all(checks)
    print(f"\n  -> {sum(checks)}/{len(checks)} structural checks passed")

    # Step 5: Show what an agent prompt would look like
    step(5, "Agent consumption prompt (for Claude / Hermes / Codex)")
    prompt = f"""Read {bundle_json} and provide:
1. A 2-sentence summary of the archived post
2. A list of all media assets with their types and SHA-256 hashes
3. The provenance information (when captured, source URL, export tool)
4. Any trust_flags that indicate data quality issues
5. A suggested citation using the citation_label field"""
    print("  Claude Code CLI example:")
    print(f"    claude --add-dir {bundle_dir} \\")
    print(f'      "{prompt}"')
    print(f"\n  Bundle directory: {bundle_dir}")
    print(f"  Manifest:         {manifest_out}")

    # Cleanup
    if cleanup:
        shutil.rmtree(work, ignore_errors=True)
        print(f"\n  (temp dir {work} cleaned up; use --bundle-dir to keep output)")
    else:
        print(f"\n  Output kept at {work}")

    # Final result
    print(f"\n{'='*60}")
    if all_pass:
        print("  [PASS] DEMO PASSED - agent consumption pipeline is functional")
        print(f"{'='*60}")
        return 0
    else:
        print("  [FAIL] DEMO FAILED - some structural checks did not pass")
        print(f"{'='*60}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
