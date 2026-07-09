"""Default schema and validation helpers for ``tweet.json``.

The schema is intentionally simple: it's a hand-written validator that
checks the **structural** invariants documented in ``CI/README.md``:

* required top-level keys
* the on-disk shape of ``media/`` and ``exports/`` actually matches
  the entries declared in the metadata.

This is *not* a generic JSON-Schema engine — it is small enough to read
in one screen and to extend when we need a new field.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from ci_common import (
    EXPORTS_DIRNAME,
    MEDIA_SUBDIRS,
    TWEET_JSON_NAME,
    is_tweet_dir,
    tweet_paths,
)


# Required and recommended fields (see CI/README.md "tweet.json 建议字段")
REQUIRED_FIELDS = (
    "tweet_id",
    "tweet_url",
    "author_handle",
    "datetime_utc",
)
RECOMMENDED_FIELDS = (
    "text",
    "media",
    "exports",
    "datetime_local",
    "components",
    "replies",
)
TWITTER_STATUS_RE = re.compile(r"/([^/]+)/status/(\d+)")


@dataclass
class ValidationIssue:
    level: str  # "error" | "warning"
    code: str
    message: str
    path: str = ""

    def render(self) -> str:
        loc = f" {self.path}" if self.path else ""
        return f"[{self.level.upper()} {self.code}]{loc} {self.message}"


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, items: Iterable[ValidationIssue]) -> None:
        self.issues.extend(items)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_tweet_dir(tweet_dir: Path) -> ValidationReport:
    """Validate a single tweet directory.

    Returns a :class:`ValidationReport`. Always non-fatal; the caller
    decides what to do with errors vs warnings.
    """
    report = ValidationReport()
    tweet_dir = tweet_dir.resolve()
    if not is_tweet_dir(tweet_dir):
        report.issues.append(ValidationIssue(
            "error", "E001",
            f"Not a tweet dir (missing {TWEET_JSON_NAME}): {tweet_dir}",
        ))
        return report

    tp = tweet_paths(tweet_dir)
    meta = _read_json(tp.tweet_json, report, "tweet.json")

    if not meta:
        # _read_json already added an issue
        return report

    _check_required_fields(meta, report, str(tp.tweet_json))
    _check_tweet_url(meta, report)
    _check_author_handle(meta, report)
    _check_datetime_utc(meta, report)
    _check_media_entries(meta, tp, report)
    _check_exports_entries(meta, tp, report)
    _check_optional_dirs(meta, tp, report)

    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path, report: ValidationReport, label: str) -> dict:
    if not path.is_file():
        report.issues.append(ValidationIssue(
            "error", "E002", f"Missing {label}: {path}", str(path),
        ))
        return {}
    try:
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # JSONDecodeError, OSError, UnicodeDecodeError
        report.issues.append(ValidationIssue(
            "error", "E003", f"Invalid JSON in {label}: {e}", str(path),
        ))
        return {}


def _truncate(value, limit: int = 80) -> str:
    """Render a value for error messages, truncating long strings."""
    if isinstance(value, str):
        s = value
    else:
        s = repr(value)
    if len(s) > limit:
        return s[: limit - 3] + "..."
    return s


def _check_required_fields(meta: dict, report: ValidationReport, where: str) -> None:
    for key in REQUIRED_FIELDS:
        if key not in meta:
            report.issues.append(ValidationIssue(
                "error", "E010",
                f"{key}: missing required field (expected non-empty string)",
                where,
            ))
        elif not meta.get(key):
            actual = _truncate(meta.get(key))
            report.issues.append(ValidationIssue(
                "error", "E010",
                f"{key}: missing required field (expected non-empty string, got {actual!r})",
                where,
            ))
    for key in RECOMMENDED_FIELDS:
        if key not in meta:
            report.issues.append(ValidationIssue(
                "warning", "W010",
                f"{key}: missing recommended field",
                where,
            ))


def _check_tweet_url(meta: dict, report: ValidationReport) -> None:
    url = meta.get("tweet_url") or ""
    if not url:
        return
    if not (url.startswith("http://") or url.startswith("https://")):
        report.issues.append(ValidationIssue(
            "error", "E020",
            f"tweet_url: expected http(s) URL, got {_truncate(url)!r}",
        ))
    m = TWITTER_STATUS_RE.search(url)
    if m:
        url_handle = m.group(1)
        author = meta.get("author_handle", "").lstrip("@")
        if author and url_handle and url_handle.lower() != author.lower():
            report.issues.append(ValidationIssue(
                "warning", "W021",
                f"tweet_url: handle in URL ({url_handle!r}) != author_handle ({author!r})",
            ))


def _check_author_handle(meta: dict, report: ValidationReport) -> None:
    h = meta.get("author_handle", "")
    if not h:
        return
    if h.startswith("@"):
        report.issues.append(ValidationIssue(
            "warning", "W030",
            f"author_handle: should not start with '@' (got {_truncate(h)!r})",
        ))


def _check_datetime_utc(meta: dict, report: ValidationReport) -> None:
    dt = meta.get("datetime_utc", "")
    if not dt:
        return
    # Tolerant: accept ISO 8601 with trailing Z; complain otherwise.
    if "T" not in dt:
        report.issues.append(ValidationIssue(
            "warning", "W040",
            f"datetime_utc: expected ISO 8601 with 'T' separator (got {_truncate(dt)!r})",
        ))


def _check_media_entries(meta: dict, tp, report: ValidationReport) -> None:
    media = meta.get("media") or []
    if not isinstance(media, list):
        report.issues.append(ValidationIssue(
            "error", "E050",
            f"media: expected list, got {type(media).__name__} ({_truncate(media)!r})",
            str(tp.tweet_json),
        ))
        return
    for idx, m in enumerate(media):
        if not isinstance(m, dict):
            report.issues.append(ValidationIssue(
                "error", "E051",
                f"media[{idx}]: expected object, got {type(m).__name__} ({_truncate(m)!r})",
            ))
            continue
        rel = m.get("file")
        if not rel:
            report.issues.append(ValidationIssue(
                "warning", "W051",
                f"media[{idx}].file: missing 'file' field",
            ))
            continue
        # Accept two common conventions:
        #   "01.jpg"                       -> resolved under images_dir by default
        #   "media/images/01.jpg"          -> resolved from tweet_dir root
        candidates: list[Path] = []
        if "/" in rel or "\\" in rel:
            candidates.append((tp.root / rel).resolve())
            # also strip a leading "media/<sub>/" and re-try under the matching subdir
            for sub in MEDIA_SUBDIRS:
                prefix = f"media/{sub}/"
                if rel.startswith(prefix) or rel.startswith(f"media\\{sub}\\"):
                    candidates.append((tp.root / "media" / sub / rel[len(prefix):]).resolve())
                    break
        else:
            for sub in MEDIA_SUBDIRS:
                candidates.append((tp.root / "media" / sub / rel).resolve())
        if not any(p.is_file() for p in candidates):
            report.issues.append(ValidationIssue(
                "error", "E052",
                f"media[{idx}].file: path does not exist on disk "
                f"(got {_truncate(rel)!r}; tried: {', '.join(str(c) for c in candidates)})",
            ))


def _check_exports_entries(meta: dict, tp, report: ValidationReport) -> None:
    exports = meta.get("exports")
    if exports is None:
        return
    if not isinstance(exports, list):
        report.issues.append(ValidationIssue(
            "error", "E060",
            f"exports: expected list, got {type(exports).__name__} ({_truncate(exports)!r})",
            str(tp.tweet_json),
        ))
        return
    for idx, e in enumerate(exports):
        if not isinstance(e, dict):
            report.issues.append(ValidationIssue(
                "error", "E061",
                f"exports[{idx}]: expected object, got {type(e).__name__} ({_truncate(e)!r})",
            ))
            continue
        rel = e.get("file")
        if not rel:
            report.issues.append(ValidationIssue(
                "warning", "W061",
                f"exports[{idx}].file: missing 'file' field",
            ))
            continue
        # Accept "foo.pdf" or "exports/foo.pdf"
        path = (tp.exports_dir / rel) if ("/" in rel or "\\" in rel and rel.lower().startswith("exports")) else (tp.exports_dir / rel)
        if not path.is_file():
            # try the original interpretation as well
            alt = tp.exports_dir / rel
            if not alt.is_file():
                report.issues.append(ValidationIssue(
                    "warning", "W062",
                    f"exports[{idx}].file: missing on disk (got {_truncate(rel)!r})",
                ))


def _check_optional_dirs(meta: dict, tp, report: ValidationReport) -> None:
    # Only complain when media[] mentions a subdir that doesn't exist.
    declared = set()
    for m in meta.get("media") or []:
        f = (m or {}).get("file", "")
        for sub in MEDIA_SUBDIRS:
            if f.startswith(f"{sub}/") or f.startswith(f"{sub}\\"):
                declared.add(sub)
                break
    for sub in declared:
        d = tp.root / "media" / sub
        if not d.is_dir():
            report.issues.append(ValidationIssue(
                "warning", "W070", f"media/{sub} referenced but dir missing",
            ))

    # If exports field is missing, don't force the dir; it's optional.
    if meta.get("exports") and not tp.exports_dir.is_dir():
        report.issues.append(ValidationIssue(
            "warning", "W071", f"exports declared but {EXPORTS_DIRNAME}/ missing",
        ))


# ---------------------------------------------------------------------------
# Update helpers (used by downloader-side tools, kept here for one source of truth)
# ---------------------------------------------------------------------------

def write_tweet_json(tweet_dir: Path, meta: dict, *, validate: bool = True) -> Path:
    """Write ``tweet.json`` in canonical JSON form.

    If ``validate`` is True (default), an exception is raised on schema
    errors so the caller can fix them before persisting.
    """
    import json
    if validate:
        # Build a fake tweet dir to use validate_tweet_dir on a not-yet-saved meta
        tp = tweet_paths(tweet_dir)
        tp.root.mkdir(parents=True, exist_ok=True)
        # write first, then validate (we want to check media/ exports/ existence)
        out = tweet_dir / TWEET_JSON_NAME
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=False),
            encoding="utf-8",
        )
        report = validate_tweet_dir(tweet_dir)
        if not report.ok:
            # Roll back to avoid leaving invalid state on disk.
            try:
                out.unlink()
            except OSError:
                pass
            msgs = "\n".join(i.render() for i in report.errors)
            raise ValueError(f"tweet.json validation failed:\n{msgs}")
        return out

    out = tweet_dir / TWEET_JSON_NAME
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, sort_keys=False),
        encoding="utf-8",
    )
    return out
