"""Data shapes for the provisioning demo.

Kept deliberately dependency-free so the planning layer can be tested
without credentials, network access or the Google client library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping


@dataclass(frozen=True)
class Employee:
    """One row of HR truth, as it arrives from the HRIS or an intake CSV."""

    email: str
    first_name: str
    last_name: str
    org_unit: str
    groups: tuple[str, ...] = ()
    license_sku: str | None = None
    start_date: date | None = None
    status: str = "active"  # "active" | "leaver"

    def __post_init__(self) -> None:
        if self.status not in ("active", "leaver"):
            raise ValueError(f"unknown status {self.status!r} for {self.email}")


@dataclass(frozen=True)
class UserState:
    """What the directory currently says about one user.

    This is the only view the planner gets of the outside world, which is
    what makes the planning layer a pure function.
    """

    email: str
    org_unit: str
    suspended: bool = False
    groups: frozenset[str] = frozenset()
    license_sku: str | None = None


@dataclass(frozen=True)
class Action:
    """A single, idempotent change to the directory."""

    kind: str
    target: str
    detail: str
    payload: Mapping[str, Any] = field(default_factory=dict)

    def describe(self) -> str:
        return f"{self.kind:<14} {self.target:<34} {self.detail}"


@dataclass(frozen=True)
class Config:
    """Tenant policy. Anything not allowed here is a planning error, not a write."""

    allowed_domains: tuple[str, ...]
    allowed_ous: tuple[str, ...]
    leavers_ou: str
    default_license_sku: str | None = None

    def check(self, employee: Employee) -> None:
        domain = employee.email.rsplit("@", 1)[-1].lower()
        if domain not in self.allowed_domains:
            raise ConfigError(
                f"{employee.email}: domain {domain!r} is not an allowed tenant domain"
            )
        if not _ou_allowed(employee.org_unit, self.allowed_ous):
            raise ConfigError(
                f"{employee.email}: org unit {employee.org_unit!r} is not on the "
                f"allowed list {self.allowed_ous}; refusing to create a shadow OU"
            )


class ConfigError(Exception):
    """Raised when input would make the directory do something unexpected."""


def _ou_allowed(org_unit: str, allowed: tuple[str, ...]) -> bool:
    """A child OU is allowed when one of its parents is.

    This is what stops a typo in an HR export from silently creating
    /Enginering and leaving a dozen people in a policy dead zone.
    """
    if "/" in allowed:
        return True
    for prefix in allowed:
        if org_unit == prefix:
            return True
        if org_unit.startswith(prefix.rstrip("/") + "/"):
            return True
    return False
