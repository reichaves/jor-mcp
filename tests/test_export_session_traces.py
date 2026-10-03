"""Tests for scripts/export_session_traces.py."""

import importlib.util
import json
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "export_session_traces.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("export_session_traces", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


est = _load_module()

SESSION_ID = "11111111-2222-3333-4444-555555555555"
HOME = "/Users/someone"


def _write_session(source: Path, records: list[dict[str, Any]]) -> Path:
    source.mkdir(parents=True, exist_ok=True)
    path = source / f"{SESSION_ID}.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def _write_index(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "| # | File | Session ID | Date | Category | Description |\n"
        "|---|---|---|---|---|---|\n"
        f"{est.INDEX_END_MARKER}\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture
def records() -> list[dict[str, Any]]:
    return [
        {"type": "permission-mode", "permissionMode": "default"},
        {"type": "attachment", "attachment": {"cwd": f"{HOME}/repo"}},
        {
            "type": "user",
            "isMeta": True,
            "message": {"role": "user", "content": "<system-reminder>ctx</system-reminder>"},
        },
        {
            "type": "user",
            "timestamp": "2026-10-03T10:00:00Z",
            "message": {"role": "user", "content": "Explain this | project"},
        },
        {
            "type": "assistant",
            "timestamp": "2026-10-03T10:00:05Z",
            "message": {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "Mail me at person@example.com"},
                    {"type": "tool_use", "input": {"command": f"cat {HOME}/repo/.env"}},
                ],
            },
        },
        {
            "type": "user",
            "message": {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "content": "MCP_GITHUB_TOKEN=ghp_abcdefghijklmnopqrstuvwxyz123456\n"
                        "Co-Authored-By: Claude <noreply@anthropic.com>",
                    }
                ],
            },
        },
    ]


def test_filter_records_keeps_only_conversation_types() -> None:
    lines = [
        json.dumps({"type": "user"}),
        json.dumps({"type": "attachment"}),
        "",
        "{broken",
        json.dumps({"type": "assistant"}),
        json.dumps(["not", "a", "dict"]),
    ]
    kept, dropped = est.filter_records(lines)
    assert [r["type"] for r in kept] == ["user", "assistant"]
    assert dropped == 3


def test_sanitizer_redacts_nested_strings() -> None:
    sanitizer = est.Sanitizer(home=HOME)
    value = {
        "a": [f"{HOME}/x and {HOME}/y", {"b": "x@y.org"}],
        "c": "key AIza" + "A" * 35,
        "d": "sk-" + "b" * 24 + " github_pat_" + "c" * 22,
        "e": 42,
        "f": "NoReply@Anthropic.com",
    }
    result = sanitizer.sanitize(value)
    assert result["a"] == ["~/x and ~/y", {"b": "<redacted-email>"}]
    assert result["c"] == "key <redacted-token>"
    assert result["d"] == "<redacted-token> <redacted-token>"
    assert result["e"] == 42
    assert result["f"] == "NoReply@Anthropic.com"
    assert sanitizer.counts == {"home_path": 2, "email": 1, "token": 3}


def test_sanitizer_redacts_partial_emails_only() -> None:
    sanitizer = est.Sanitizer(home="")
    result = sanitizer.sanitize("grep 'person@gmail' f; HEAD@{1}; x @decorator; v@1.2")
    assert result == "grep '<redacted-email>' f; HEAD@{1}; x @decorator; v@1.2"
    assert sanitizer.counts == {"email": 1}


def test_sanitizer_redacts_username() -> None:
    sanitizer = est.Sanitizer(home=HOME, username="someone")
    result = sanitizer.sanitize(f"{HOME}/a -Users-someone-repo drwx 1 someone staff")
    assert result == "~/a -Users-<user>-repo drwx 1 <user> staff"
    assert sanitizer.counts == {"home_path": 1, "username": 2}


def test_sanitizer_with_empty_home_leaves_paths() -> None:
    assert est.Sanitizer(home="").sanitize("/Users/x") == "/Users/x"


def test_first_user_prompt_and_timestamp() -> None:
    records = [
        {"type": "assistant", "message": {"content": "hi"}},
        {"type": "user", "isMeta": True, "message": {"content": "meta"}},
        {"type": "user", "message": {"content": "<command-name>/init</command-name>"}},
        {"type": "user", "message": "not a dict"},
        {"type": "user", "message": {"content": [{"type": "image"}]}},
        {"type": "user", "message": {"content": 7}},
        {
            "type": "user",
            "timestamp": "2026-10-03T10:00:00Z",
            "message": {"content": [{"type": "text", "text": "  Real prompt "}]},
        },
    ]
    assert est.first_user_prompt(records) == "Real prompt"
    assert est.first_user_prompt([]) == ""
    assert est.first_timestamp(records) == "2026-10-03"
    assert est.first_timestamp([{"timestamp": 1}]) == ""


def test_slugify() -> None:
    assert est.slugify("Do que se trata este projeto? Explique tudo agora") == (
        "do-que-se-trata-este-projeto"
    )
    assert est.slugify("???") == "session"


def test_default_source_dir() -> None:
    result = est.default_source_dir(Path("/Users/me/Code/jor-mcp"))
    assert result == Path.home() / ".claude" / "projects" / "-Users-me-Code-jor-mcp"


def test_export_session_writes_sanitized_trace_and_index(
    tmp_path: Path, records: list[dict[str, Any]]
) -> None:
    source = _write_session(tmp_path / "src", records)
    with source.open("a", encoding="utf-8") as handle:
        handle.write("not json\n")
    traces_dir = tmp_path / "traces"
    index = _write_index(traces_dir / "README.md")
    sanitizer = est.Sanitizer(home=HOME)

    target = est.export_session(source, traces_dir, index, sanitizer)

    assert target.name == "trace-01-explain-this-project.jsonl"
    lines = target.read_text(encoding="utf-8").splitlines()
    exported = [json.loads(line) for line in lines]
    assert {r["type"] for r in exported} <= {"user", "assistant", "system"}
    assert len(exported) == 4
    text = target.read_text(encoding="utf-8")
    assert HOME not in text
    assert "person@example.com" not in text
    assert "ghp_" not in text
    assert "noreply@anthropic.com" in text

    index_text = index.read_text(encoding="utf-8")
    assert (
        f"| 01 | `trace-01-explain-this-project.jsonl` | `{SESSION_ID}` | 2026-10-03 | TODO | "
        "Explain this \\| project |" in index_text
    )
    assert index_text.index(SESSION_ID) < index_text.index(est.INDEX_END_MARKER)


def test_export_session_is_idempotent(tmp_path: Path, records: list[dict[str, Any]]) -> None:
    source = _write_session(tmp_path / "src", records)
    traces_dir = tmp_path / "traces"
    index = _write_index(traces_dir / "README.md")

    first = est.export_session(source, traces_dir, index, est.Sanitizer(home=HOME), "custom")
    second = est.export_session(source, traces_dir, index, est.Sanitizer(home=HOME), "other")

    assert first == second
    assert first.name == "trace-01-custom.jsonl"
    assert index.read_text(encoding="utf-8").count(SESSION_ID) == 1
    assert sorted(p.name for p in traces_dir.glob("*.jsonl")) == ["trace-01-custom.jsonl"]


def test_export_session_numbers_after_existing_rows(tmp_path: Path) -> None:
    source = _write_session(tmp_path / "src", [{"type": "user", "message": {"content": ""}}])
    traces_dir = tmp_path / "traces"
    index = _write_index(traces_dir / "README.md")
    old_row = "| 07 | `trace-07-old.jsonl` | `old-session` | 2026-01-01 | X | Y |"
    est.append_index_row(index, old_row)

    target = est.export_session(source, traces_dir, index, est.Sanitizer(home=HOME))

    assert target.name == "trace-08-session.jsonl"
    assert f"`{SESSION_ID}` |  | TODO | TODO |" in index.read_text(encoding="utf-8")


def test_append_index_row_requires_marker(tmp_path: Path) -> None:
    index = tmp_path / "README.md"
    index.write_text("no marker here", encoding="utf-8")
    with pytest.raises(ValueError, match="missing the marker"):
        est.append_index_row(index, "| row |")


def test_main_exports_from_source(
    tmp_path: Path,
    records: list[dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source_dir = tmp_path / "src"
    _write_session(source_dir, records)
    traces_dir = tmp_path / "traces"
    index = _write_index(traces_dir / "README.md")
    monkeypatch.setattr(est, "TRACES_DIR", traces_dir)
    monkeypatch.setattr(est, "INDEX_PATH", index)

    assert est.main(["--source", str(source_dir)]) == 0
    assert est.main(["--source", str(source_dir), "--session", SESSION_ID]) == 0
    assert "Redactions:" in capsys.readouterr().out
    assert len(list(traces_dir.glob("*.jsonl"))) == 1


def test_main_reports_missing_sessions(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert est.main(["--source", str(tmp_path)]) == 1
    assert est.main(["--source", str(tmp_path), "--session", "nope"]) == 1
    assert "No session transcripts found" in capsys.readouterr().err
