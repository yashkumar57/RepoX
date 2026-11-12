"""Safely remove duplicate local checkouts of one GitHub repository.

Run with --apply to keep the selected repository ID and remove its duplicates.
The script backs up the SQLite database before changing anything.
"""

from __future__ import annotations

import argparse
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_KEEP_ID = "09746f8bef6e4b54ae4d0f2b034f3db9"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keep",
        default=DEFAULT_KEEP_ID,
        help="Repository ID to retain",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Perform deletion; otherwise preview",
    )
    args = parser.parse_args()

    root = Path.home() / ".repox"
    database = root / "repox.sqlite3"
    workspace = root / "repositories"
    if not database.is_file():
        parser.error(f"Workspace database not found: {database}")

    connection = sqlite3.connect(database)
    try:
        rows = connection.execute(
            "SELECT repository_id, owner, name, url FROM repositories "
            "ORDER BY created_at, repository_id"
        ).fetchall()
        keeper = next((row for row in rows if row[0] == args.keep), None)
        if keeper is None:
            parser.error(f"Keep ID does not exist in the database: {args.keep}")
        duplicates = [
            row for row in rows if row[0] != args.keep and row[1:4] == keeper[1:4]
        ]
        print(f"Keeping: {keeper[0]} ({keeper[1]}/{keeper[2]})")
        print(f"Duplicates to remove: {len(duplicates)}")
        for row in duplicates:
            print(f"  {row[0]}")
        if not args.apply:
            print(
                "Preview only. Re-run with --apply to delete duplicate "
                "records and checkouts."
            )
            return 0

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = database.with_name(f"repox.sqlite3.backup-{timestamp}")
        shutil.copy2(database, backup)
        print(f"Database backup: {backup}")

        ids = [row[0] for row in duplicates]
        for repository_id in ids:
            # Only remove a direct child with a generated RepoX ID.
            valid_id = len(repository_id) == 32 and all(
                char in "0123456789abcdef" for char in repository_id
            )
            if not valid_id:
                raise RuntimeError(f"Refusing unsafe repository ID: {repository_id}")
            checkout = (workspace / repository_id).resolve()
            if checkout.parent != workspace.resolve():
                raise RuntimeError(
                    f"Refusing path outside repository workspace: {checkout}"
                )

        with connection:
            connection.executemany(
                "DELETE FROM repositories WHERE repository_id = ?",
                [(repository_id,) for repository_id in ids],
            )
        for repository_id in ids:
            checkout = workspace / repository_id
            if checkout.exists():
                shutil.rmtree(checkout, ignore_errors=False)
        print(
            f"Removed {len(ids)} duplicate metadata records and checkout directories."
        )
        print(f"Retained repository ID: {args.keep}")
        return 0
    finally:
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
