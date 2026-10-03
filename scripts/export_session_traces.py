"""Export Claude Code session transcripts into ``traces/`` as sanitized JSONL.

Claude Code stores each session for this repository as a JSONL file under
``~/.claude/projects/<repo-path-with-dashes>/``. This script copies those
sessions into ``traces/trace-NN-<slug>.jsonl`` so the development process is
documented alongside the code, and registers each one in the index table of
``traces/README.md``.

Unlike a raw copy, every exported session is sanitized:

* Only conversation records (``user``, ``assistant``, ``system``) are kept.
  Harness metadata (environment snapshots, skill listings, file-history
  snapshots, UI state) is dropped.
* The home directory is replaced with ``~``, any other occurrence of the
  local username with ``<user>``, email addresses with ``<redacted-email>``
  and common API token shapes with ``<redacted-token>``.

Re-exporting a session that is already listed in the index overwrites its
existing file, so the script is safe to run repeatedly.

Usage:
    # Export every session recorded for this repository:
    uv run python scripts/export_session_traces.py

    # Export a single session with a descriptive file name:
    uv run python scripts/export_session_traces.py \\
        --session dfa9571b-24f9-4249-8b32-c6d043c8df66 --slug docs-firestore-native-mode
"""

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
TRACES_DIR = REPO_ROOT / "traces"
INDEX_PATH = TRACES_DIR / "README.md"
INDEX_END_MARKER = "<!-- trace-index:end -->"

KEPT_RECORD_TYPES: frozenset[str] = frozenset({"user", "assistant", "system"})

# Emails that are part of public commit metadata and carry no personal data.
ALLOWED_EMAILS: frozenset[str] = frozenset({"noreply@anthropic.com"})

# The top-level domain is optional so partial addresses (e.g. "name@gmail" typed
# in a grep command) are caught too; the domain must start with a letter.
_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z0-9-]*(?:\.[A-Za-z0-9-]+)*")
_TOKEN_RE = re.compile(
    r"ghp_[A-Za-z0-9]{20,}"
    r"|github_pat_[A-Za-z0-9_]{20,}"
    r"|AIza[0-9A-Za-z_-]{30,}"
    r"|sk-[A-Za-z0-9_-]{20,}"
)
_INDEX_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*`([^`]+)`\s*\|\s*`([^`]+)`\s*\|")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class Sanitizer:
    """Redact personal data from transcript records and count what was removed.

    Attributes:
        home: Absolute home directory path to replace with ``~``.
        username: Local account name to replace with ``<user>`` wherever it
            still appears (e.g. ``ls -l`` owner column, dashed project paths).
        counts: Number of redactions applied, keyed by kind.
    """

    home: str
    username: str = ""
    counts: Counter[str] = field(default_factory=Counter)

    def _sanitize_text(self, text: str) -> str:
        if self.home and self.home in text:
            self.counts["home_path"] += text.count(self.home)
            text = text.replace(self.home, "~")
        if self.username and self.username in text:
            self.counts["username"] += text.count(self.username)
            text = text.replace(self.username, "<user>")

        def _email(match: re.Match[str]) -> str:
            if match.group(0).lower() in ALLOWED_EMAILS:
                return match.group(0)
            self.counts["email"] += 1
            return "<redacted-email>"

        def _token(match: re.Match[str]) -> str:
            self.counts["token"] += 1
            return "<redacted-token>"

        text = _EMAIL_RE.sub(_email, text)
        return _TOKEN_RE.sub(_token, text)

    def sanitize(self, value: Any) -> Any:
        """Return a copy of *value* with every nested string sanitized.

        Args:
            value: Any JSON-compatible value (dict, list, str, number, ...).

        Returns:
            The sanitized value with the same structure.
        """
        if isinstance(value, str):
            return self._sanitize_text(value)
        if isinstance(value, list):
            return [self.sanitize(item) for item in value]
        if isinstance(value, dict):
            return {key: self.sanitize(item) for key, item in value.items()}
        return value


def default_source_dir(repo_root: Path = REPO_ROOT) -> Path:
    """Return the Claude Code project directory that stores this repo's sessions.

    Args:
        repo_root: Absolute path of the repository.

    Returns:
        ``~/.claude/projects/<repo path with "/" replaced by "-">``.
    """
    return Path.home() / ".claude" / "projects" / str(repo_root).replace("/", "-")


def filter_records(lines: list[str]) -> tuple[list[dict[str, Any]], int]:
    """Parse JSONL lines and keep only conversation records.

    Args:
        lines: Raw lines of a session transcript.

    Returns:
        A tuple of (kept records, number of dropped lines).
    """
    kept: list[dict[str, Any]] = []
    dropped = 0
    for line in lines:
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            dropped += 1
            continue
        if isinstance(record, dict) and record.get("type") in KEPT_RECORD_TYPES:
            kept.append(record)
        else:
            dropped += 1
    return kept, dropped


def _record_text(record: dict[str, Any]) -> str:
    message = record.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                return str(part.get("text", ""))
    return ""


def first_user_prompt(records: list[dict[str, Any]]) -> str:
    """Return the first prompt typed by the user, skipping harness-injected text.

    Args:
        records: Sanitized conversation records.

    Returns:
        The prompt text, or an empty string if none is found.
    """
    for record in records:
        if record.get("type") != "user" or record.get("isMeta"):
            continue
        text = _record_text(record).strip()
        if text and not text.startswith("<"):
            return text
    return ""


def first_timestamp(records: list[dict[str, Any]]) -> str:
    """Return the date (``YYYY-MM-DD``) of the first timestamped record, or ``""``."""
    for record in records:
        timestamp = record.get("timestamp")
        if isinstance(timestamp, str) and len(timestamp) >= 10:
            return timestamp[:10]
    return ""


def slugify(text: str, max_words: int = 6) -> str:
    """Build a short kebab-case slug from free text."""
    words = _SLUG_RE.sub(" ", text.lower()).split()
    return "-".join(words[:max_words]) or "session"


def read_index(index_path: Path) -> dict[str, tuple[int, str]]:
    """Map session IDs already listed in the index to (number, file name).

    Args:
        index_path: Path to ``traces/README.md``.

    Returns:
        A dict keyed by session ID.
    """
    entries: dict[str, tuple[int, str]] = {}
    for line in index_path.read_text(encoding="utf-8").splitlines():
        match = _INDEX_ROW_RE.match(line)
        if match:
            entries[match.group(3)] = (int(match.group(1)), match.group(2))
    return entries


def append_index_row(index_path: Path, row: str) -> None:
    """Insert *row* just before the index end marker in ``traces/README.md``.

    Raises:
        ValueError: If the end marker is missing from the index file.
    """
    content = index_path.read_text(encoding="utf-8")
    if INDEX_END_MARKER not in content:
        raise ValueError(f"{index_path} is missing the marker {INDEX_END_MARKER!r}")
    content = content.replace(INDEX_END_MARKER, f"{row}\n{INDEX_END_MARKER}", 1)
    index_path.write_text(content, encoding="utf-8")


def export_session(
    session_file: Path,
    traces_dir: Path,
    index_path: Path,
    sanitizer: Sanitizer,
    slug: str | None = None,
) -> Path:
    """Sanitize one session transcript and write it into *traces_dir*.

    Args:
        session_file: Source ``<session-id>.jsonl`` file.
        traces_dir: Destination directory.
        index_path: Index file listing exported traces.
        sanitizer: Sanitizer used for redaction (accumulates counts).
        slug: Optional file-name slug; derived from the first prompt when omitted.

    Returns:
        Path of the written trace file.
    """
    session_id = session_file.stem
    records, dropped = filter_records(session_file.read_text(encoding="utf-8").splitlines())
    records = [sanitizer.sanitize(record) for record in records]

    index = read_index(index_path)
    prompt = first_user_prompt(records)
    if session_id in index:
        number, file_name = index[session_id]
    else:
        number = max((n for n, _ in index.values()), default=0) + 1
        file_name = f"trace-{number:02d}-{slug or slugify(prompt)}.jsonl"
        description = " ".join(prompt.split())[:120].replace("|", "\\|") or "TODO"
        append_index_row(
            index_path,
            f"| {number:02d} | `{file_name}` | `{session_id}` | "
            f"{first_timestamp(records)} | TODO | {description} |",
        )

    target = traces_dir / file_name
    with target.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(f"{target.name}: kept {len(records)} records, dropped {dropped}")
    return target


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--source", type=Path, default=default_source_dir())
    parser.add_argument("--session", help="Export only this session ID")
    parser.add_argument("--slug", help="File-name slug for a new trace (with --session)")
    args = parser.parse_args(argv)

    if args.session:
        session_files = [args.source / f"{args.session}.jsonl"]
    else:
        session_files = sorted(args.source.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    missing = [p for p in session_files if not p.is_file()]
    if missing or not session_files:
        print(f"No session transcripts found: {missing or args.source}", file=sys.stderr)
        return 1

    sanitizer = Sanitizer(home=str(Path.home()), username=Path.home().name)
    for session_file in session_files:
        export_session(session_file, TRACES_DIR, INDEX_PATH, sanitizer, args.slug)
    print(f"Redactions: {dict(sanitizer.counts) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
