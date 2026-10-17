"""Tests for scripts/revoke_user.py."""

import importlib.util
from collections.abc import Generator
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from firebase_admin import auth

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "revoke_user.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("revoke_user", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ru = _load_module()

EMAIL = "user@domain.com"
UID = "uid-123"


def _make_db(*, doc_exists: bool) -> tuple[MagicMock, MagicMock]:
    """Return a fake Firestore client and the document reference it hands out."""
    doc_ref = MagicMock()
    doc_ref.get.return_value.exists = doc_exists
    db = MagicMock()
    db.collection.return_value.document.return_value = doc_ref
    return db, doc_ref


@pytest.fixture
def firebase_auth() -> Generator[dict[str, MagicMock], None, None]:
    """Patch the three Firebase Auth calls the script makes."""
    with (
        patch.object(auth, "get_user_by_email") as get_user,
        patch.object(auth, "set_custom_user_claims") as set_claims,
        patch.object(auth, "revoke_refresh_tokens") as revoke,
    ):
        get_user.return_value.uid = UID
        yield {"get_user": get_user, "set_claims": set_claims, "revoke": revoke}


def test_revoke_user_runs_all_three_steps(firebase_auth: dict[str, MagicMock]) -> None:
    """The email is normalized, then the document, claims and sessions are revoked."""
    db, doc_ref = _make_db(doc_exists=True)

    report = ru.revoke_user("  User@Domain.com ", db)

    db.collection.assert_called_once_with(ru.ALLOWED_USERS_COLLECTION)
    db.collection.return_value.document.assert_called_once_with(EMAIL)
    doc_ref.update.assert_called_once_with({"status": "disabled"})
    firebase_auth["get_user"].assert_called_once_with(EMAIL)
    firebase_auth["set_claims"].assert_called_once_with(UID, None)
    firebase_auth["revoke"].assert_called_once_with(UID)
    assert len(report) == 3
    assert not any(line.startswith("[dry-run]") for line in report)


def test_revoke_user_dry_run_changes_nothing(firebase_auth: dict[str, MagicMock]) -> None:
    """--dry-run looks the user up but writes nothing."""
    db, doc_ref = _make_db(doc_exists=True)

    report = ru.revoke_user(EMAIL, db, dry_run=True)

    doc_ref.update.assert_not_called()
    firebase_auth["set_claims"].assert_not_called()
    firebase_auth["revoke"].assert_not_called()
    assert len(report) == 3
    assert all(line.startswith("[dry-run]") for line in report)


def test_revoke_user_unknown_user(firebase_auth: dict[str, MagicMock]) -> None:
    """With no document and no Firebase account, nothing is written and both are reported."""
    db, doc_ref = _make_db(doc_exists=False)
    firebase_auth["get_user"].side_effect = auth.UserNotFoundError("not found")

    report = ru.revoke_user(EMAIL, db)

    doc_ref.update.assert_not_called()
    firebase_auth["set_claims"].assert_not_called()
    firebase_auth["revoke"].assert_not_called()
    assert report == [
        f"no {ru.ALLOWED_USERS_COLLECTION}/{EMAIL} document; nothing to disable",
        "no Firebase account for this email; no claim or session to revoke",
    ]


def test_main_initializes_firebase_and_prints_report(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main() initializes the Admin SDK when needed and prints one line per step."""
    with (
        patch.object(ru.firebase_admin, "get_app", side_effect=ValueError("No app")),
        patch.object(ru.firebase_admin, "initialize_app") as init,
        patch.object(ru, "FirestoreClient") as client_cls,
        patch.object(ru, "revoke_user", return_value=["step one", "step two"]) as revoke,
    ):
        exit_code = ru.main([EMAIL, "--dry-run"])

    assert exit_code == 0
    init.assert_called_once()
    client_cls.assert_called_once_with(database=ru.FIRESTORE_DATABASE_ID)
    revoke.assert_called_once_with(EMAIL, client_cls.return_value, dry_run=True)
    assert capsys.readouterr().out == "step one\nstep two\n"
