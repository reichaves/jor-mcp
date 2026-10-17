"""Revoke a user's access to this jor-mcp instance in one step.

Editing ``allowed_users`` alone is not enough to end someone's access right
away. This script runs the three revocation steps from the deployment guide
(section 5.2):

1. Set ``status`` to ``"disabled"`` in the user's ``allowed_users`` document.
2. Remove the ``tier`` custom claim from the user's Firebase account.
3. Revoke the user's refresh tokens.

An ID token issued before the revocation stays valid until it expires (at most
one hour).

Run it with Application Default Credentials that hold ``roles/datastore.user``
and ``roles/firebaseauth.admin`` on the project, and with the same
``FIRESTORE_DATABASE_ID`` and ``ALLOWED_USERS_COLLECTION`` as the server.

Usage:
    uv run --env-file .env python scripts/revoke_user.py user@domain.com
    uv run --env-file .env python scripts/revoke_user.py user@domain.com --dry-run
"""

import argparse
import sys
from pathlib import Path
from typing import cast

import firebase_admin
from firebase_admin import auth
from google.cloud.firestore_v1 import Client as FirestoreClient
from google.cloud.firestore_v1 import DocumentSnapshot

REPO_ROOT = Path(__file__).resolve().parent.parent
# Scripts run from scripts/, where the src package is not importable by default.
sys.path.insert(0, str(REPO_ROOT))

from src.config import ALLOWED_USERS_COLLECTION, FIRESTORE_DATABASE_ID  # noqa: E402


def revoke_user(email: str, db: FirestoreClient, *, dry_run: bool = False) -> list[str]:
    """Run the three revocation steps for *email* and describe each one.

    Args:
        email: The user's Google email; matched in lowercase, like the server.
        db: A Firestore client for the instance's database.
        dry_run: When True, only look the user up and report what would change.

    Returns:
        One human-readable line per step.
    """
    normalized = email.strip().lower()
    prefix = "[dry-run] would " if dry_run else ""
    report: list[str] = []

    doc_ref = db.collection(ALLOWED_USERS_COLLECTION).document(normalized)
    # The sync client always returns a snapshot; the stubs also allow an awaitable.
    if cast(DocumentSnapshot, doc_ref.get()).exists:
        if not dry_run:
            doc_ref.update({"status": "disabled"})
        report.append(f"{prefix}set status=disabled in {ALLOWED_USERS_COLLECTION}/{normalized}")
    else:
        report.append(f"no {ALLOWED_USERS_COLLECTION}/{normalized} document; nothing to disable")

    try:
        user = auth.get_user_by_email(normalized)
    except auth.UserNotFoundError:
        report.append("no Firebase account for this email; no claim or session to revoke")
        return report

    if not dry_run:
        auth.set_custom_user_claims(user.uid, None)
    report.append(f"{prefix}remove custom claims from Firebase user {user.uid}")
    if not dry_run:
        auth.revoke_refresh_tokens(user.uid)
    report.append(f"{prefix}revoke refresh tokens of Firebase user {user.uid}")
    return report


def main(argv: list[str] | None = None) -> int:
    """Command-line entry point."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("email", help="Google email of the user to revoke")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would change without changing it"
    )
    args = parser.parse_args(argv)

    try:
        firebase_admin.get_app()
    except ValueError:
        firebase_admin.initialize_app()
    db = FirestoreClient(database=FIRESTORE_DATABASE_ID)

    for line in revoke_user(args.email, db, dry_run=args.dry_run):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
