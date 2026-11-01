"""Command line entry point.

    python -m provisioner.cli --input data/new_hires.example.csv \
        --snapshot data/snapshot.example.json          # dry run, no credentials

    python -m provisioner.cli --input ... --fake --apply   # execute against the
                                                           # in-memory directory
"""

from __future__ import annotations

import argparse
import csv
import sys
from datetime import date, datetime
from pathlib import Path

from .directory import FakeDirectory, GoogleDirectory, load_snapshot
from .models import Config, ConfigError, Employee, UserState
from .plan import build_plan, summarise

DEFAULT_CONFIG = Config(
    allowed_domains=("example.com",),
    allowed_ous=("/Engineering", "/Operations", "/Leavers"),
    leavers_ou="/Leavers",
    default_license_sku="Google-Apps-For-Business",
)


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"unparseable date {value!r}")


def load_employees(path: str | Path) -> list[Employee]:
    employees: list[Employee] = []
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            groups = tuple(g.strip() for g in (row.get("groups") or "").split(";") if g.strip())
            employees.append(
                Employee(
                    email=row["email"].strip(),
                    first_name=row["first_name"].strip(),
                    last_name=row["last_name"].strip(),
                    org_unit=row["org_unit"].strip(),
                    groups=groups,
                    license_sku=(row.get("license_sku") or "").strip() or None,
                    start_date=parse_date(row.get("start_date")),
                    status=(row.get("status") or "active").strip().lower(),
                )
            )
    return employees


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile Google Workspace with HR.")
    parser.add_argument("--input", required=True, help="HR export (CSV)")
    parser.add_argument("--snapshot", help="saved directory snapshot (JSON) for offline dry runs")
    parser.add_argument("--apply", action="store_true", help="write changes (default is a dry run)")
    parser.add_argument("--fake", action="store_true", help="apply against the in-memory directory")
    parser.add_argument("--admin-email", help="super admin to impersonate via domain-wide delegation")
    args = parser.parse_args(argv)

    try:
        employees = load_employees(args.input)
    except (OSError, KeyError, ValueError) as exc:
        print(f"input error: {exc}", file=sys.stderr)
        return 2

    if args.fake:
        seeded = list(load_snapshot(args.snapshot).values()) if args.snapshot else []
        directory: FakeDirectory | GoogleDirectory = FakeDirectory(seeded, retry_calls=0)
    elif args.apply:
        directory = GoogleDirectory(admin_email=args.admin_email)
    else:
        if not args.snapshot:
            print(
                "dry run needs --snapshot (or pass --fake / --apply); refusing to invent a directory",
                file=sys.stderr,
            )
            return 2
        directory = None  # type: ignore[assignment]

    try:
        if directory is None:
            snapshot: dict[str, UserState] = load_snapshot(args.snapshot)
        else:
            snapshot = directory.snapshot()
        plan = build_plan(employees, snapshot, DEFAULT_CONFIG)
    except ConfigError as exc:
        print(f"refusing to plan: {exc}", file=sys.stderr)
        return 2

    print(summarise(plan) + "\n")

    if not args.apply:
        print("dry run — nothing was written. Re-run with --apply to execute.")
        return 0

    if directory is None:
        print("--apply needs a directory client (--fake or a real one)", file=sys.stderr)
        return 2

    for action in plan:
        directory.execute(action)

    # Prove idempotency on the spot instead of claiming it.
    leftover = build_plan(employees, directory.snapshot(), DEFAULT_CONFIG)
    print(f"applied {len(plan)} action(s); second pass: {len(leftover)} remaining")
    return 0 if not leftover else 1


if __name__ == "__main__":
    raise SystemExit(main())
