"""Execution layer: retries, an offline fake directory, and the real Admin SDK.

The `googleapiclient` import lives inside `GoogleDirectory.__init__` so this
module — and its tests — run on a machine with no Google packages at all.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from .models import Action, UserState

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})


class RetryableError(Exception):
    """What the retry helper raises when it gives up."""


def _status_of(exc: BaseException) -> int | None:
    """Dig a HTTP status out of whatever the client library raised.

    Deliberately duck-typed: the Admin SDK raises `HttpError` (with `.resp`),
    `google.api_core` raises status-aware exceptions, and anything else is
    simply not retryable.
    """
    for attr in ("status", "status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    resp = getattr(exc, "resp", None)
    status = getattr(resp, "status", None)
    if status is not None:
        try:
            return int(status)
        except (TypeError, ValueError):
            return None
    return None


def _retry_after_seconds(exc: BaseException) -> float | None:
    resp = getattr(exc, "resp", None)
    headers = getattr(resp, "get", None)
    if headers is None:
        return None
    raw = resp.get("retry-after")
    if raw is None:
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def call_with_retry(
    fn: Callable[[], Any],
    *,
    max_attempts: int = 5,
    base_delay: float = 0.5,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Call `fn`, retrying quota and server errors with exponential backoff.

    Google's Directory API answers a burst of writes with 429s, and a bulk
    onboarding run is exactly that burst. Without this the run dies on the
    first rate limit; with a plain `time.sleep(1)` retry it dies again.
    """
    last_error: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - re-raised below if not retryable
            status = _status_of(exc)
            if status not in RETRYABLE_STATUS:
                raise
            last_error = exc
            if attempt == max_attempts:
                break
            delay = _retry_after_seconds(exc) or base_delay * (2 ** (attempt - 1))
            sleep(delay)
    raise RetryableError(
        f"giving up after {max_attempts} attempts, last status {_status_of(last_error) if last_error else '?'}"
    ) from last_error


class FakeDirectory:
    """In-memory stand-in for the Admin SDK.

    Used by the tests and by `--fake` runs, so the whole pipeline can be
    demonstrated to someone with no credentials and no tenant.
    """

    def __init__(self, users: Iterable[UserState] = (), *, retry_calls: int = 0) -> None:
        self.users: dict[str, UserState] = {u.email.lower(): u for u in users}
        self.calls: list[Action] = []
        # Number of initial calls to fail with a 429, to exercise the retry path.
        self.retry_calls = retry_calls
        self._attempts = 0

    # -- snapshot -----------------------------------------------------------
    def snapshot(self) -> dict[str, UserState]:
        return dict(self.users)

    # -- execution ----------------------------------------------------------
    def execute(self, action: Action) -> None:
        self._attempts += 1
        if self._attempts <= self.retry_calls:
            raise FakeHttpError(429, retry_after=0)

        key = action.target.lower() if action.kind != "add_to_group" and action.kind != "remove_from_group" else None

        if action.kind == "create_user":
            email = action.payload["primaryEmail"]
            name = action.payload.get("name", {})
            self.users[email.lower()] = UserState(
                email=email,
                org_unit=action.payload["orgUnitPath"],
                suspended=False,
            )
        elif action.kind == "move_user":
            user = self._user(key)
            self.users[key] = _replace(user, org_unit=action.payload["orgUnitPath"])
        elif action.kind == "suspend_user":
            self.users[key] = _replace(self._user(key), suspended=True)
        elif action.kind == "unsuspend_user":
            self.users[key] = _replace(self._user(key), suspended=False)
        elif action.kind == "add_to_group":
            email = action.payload["email"].lower()
            user = self._user(email)
            self.users[email] = _replace(user, groups=user.groups | {action.target})
        elif action.kind == "remove_from_group":
            email = action.payload["email"].lower()
            user = self._user(email)
            self.users[email] = _replace(user, groups=user.groups - {action.target})
        elif action.kind == "assign_license":
            self.users[key] = _replace(self._user(key), license_sku=action.payload["skuId"])
        else:
            raise ValueError(f"unknown action kind {action.kind!r}")

        self.calls.append(action)

    def _user(self, key: str | None) -> UserState:
        if key is None or key not in self.users:
            raise KeyError(f"no such user {key!r}; plan ran out of order")
        return self.users[key]


class FakeHttpError(Exception):
    def __init__(self, status: int, *, retry_after: float | None = None) -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.resp = {"status": str(status)}
        if retry_after is not None:
            self.resp["retry-after"] = str(retry_after)


class GoogleDirectory:
    """Thin wrapper over the Admin SDK Directory API.

    Only the calls this demo plans for; a real deployment would grow this
    into a small library with its own contract tests.
    """

    def __init__(self, service: Any = None, admin_email: str | None = None) -> None:
        if service is None:
            from google.oauth2 import service_account  # noqa: PLC0415
            from googleapiclient.discovery import build  # noqa: PLC0415

            credentials = service_account.Credentials.from_service_account_file(
                "credentials.json",
                scopes=[
                    "https://www.googleapis.com/auth/admin.directory.user",
                    "https://www.googleapis.com/auth/admin.directory.group.member",
                    "https://www.googleapis.com/auth/apps.licensing",
                ],
                subject=admin_email,
            )
            service = build("admin", "directory_v1", credentials=credentials, cache_discovery=False)
        self.service = service

    def snapshot(self) -> dict[str, UserState]:
        users: dict[str, UserState] = {}
        request = self.service.users().list(
            customer="my_customer", maxResults=500, projection="full", orderBy="email"
        )
        while request is not None:
            response = call_with_retry(request.execute)
            for item in response.get("users", []):
                users[item["primaryEmail"].lower()] = UserState(
                    email=item["primaryEmail"],
                    org_unit=item.get("orgUnitPath", "/"),
                    suspended=bool(item.get("suspended")),
                )
            request = self.service.users().list_next(request, response)
        return users

    def execute(self, action: Action) -> None:
        call_with_retry(lambda: self._dispatch(action).execute())

    def _dispatch(self, action: Action) -> Any:
        users = self.service.users()
        email = action.target if action.kind not in ("add_to_group", "remove_from_group") else None
        if action.kind == "create_user":
            return users.insert(body=dict(action.payload))
        if action.kind == "move_user":
            return users.update(userKey=email, body={"orgUnitPath": action.payload["orgUnitPath"]})
        if action.kind == "suspend_user":
            return users.update(userKey=email, body={"suspended": True})
        if action.kind == "unsuspend_user":
            return users.update(userKey=email, body={"suspended": False})
        if action.kind == "add_to_group":
            return self.service.members().insert(groupKey=action.target, body={"email": action.payload["email"]})
        if action.kind == "remove_from_group":
            return self.service.members().delete(groupKey=action.target, memberKey=action.payload["email"])
        if action.kind == "assign_license":
            return self.service.licensing().licenseAssignments().insert(
                productId="Google-Apps", skuId=action.payload["skuId"], body={"userId": email}
            )
        raise ValueError(f"unknown action kind {action.kind!r}")


def _replace(user: UserState, **changes: Any) -> UserState:
    data = {
        "email": user.email,
        "org_unit": user.org_unit,
        "suspended": user.suspended,
        "groups": user.groups,
        "license_sku": user.license_sku,
    }
    data.update(changes)
    return UserState(**data)


def load_snapshot(path: str | Path) -> dict[str, UserState]:
    """Read a saved directory snapshot, so a demo needs no tenant and no keys."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return {
        item["email"].lower(): UserState(
            email=item["email"],
            org_unit=item.get("org_unit", "/"),
            suspended=bool(item.get("suspended", False)),
            groups=frozenset(item.get("groups", [])),
            license_sku=item.get("license_sku"),
        )
        for item in raw["users"]
    }


def dump_snapshot(users: Mapping[str, UserState], path: str | Path) -> None:
    payload = {
        "users": [
            {
                "email": u.email,
                "org_unit": u.org_unit,
                "suspended": u.suspended,
                "groups": sorted(u.groups),
                "license_sku": u.license_sku,
            }
            for u in users.values()
        ]
    }
    Path(path).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
