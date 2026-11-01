"""The planner: pure functions from (HR rows, directory snapshot) to actions.

No network, no credentials, no Google imports. That is deliberate — the part
that decides *what* should happen is the part that deserves tests, and it can
be tested exhaustively when it has no side effects.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .models import Action, Config, Employee, UserState


def build_plan(
    employees: Iterable[Employee],
    snapshot: Mapping[str, UserState],
    config: Config,
) -> list[Action]:
    """Return the minimal set of actions that makes the directory match HR.

    Running this twice against the same snapshot must yield the same plan, and
    running it against the snapshot *after* applying the plan must yield an
    empty one. Both properties are asserted in tests/test_plan.py.
    """
    actions: list[Action] = []
    for employee in employees:
        config.check(employee)
        current = snapshot.get(employee.email.lower())
        if employee.status == "leaver":
            actions.extend(_plan_leaver(employee, current, config))
        else:
            actions.extend(_plan_active(employee, current, config))
    return actions


def _plan_active(employee: Employee, current: UserState | None, config: Config) -> list[Action]:
    actions: list[Action] = []

    if current is None:
        actions.append(
            Action(
                kind="create_user",
                target=employee.email,
                detail=f"{employee.first_name} {employee.last_name} -> {employee.org_unit}",
                payload={
                    "primaryEmail": employee.email,
                    "name": {"givenName": employee.first_name, "familyName": employee.last_name},
                    "orgUnitPath": employee.org_unit,
                    "changePasswordAtNextLogin": True,
                },
            )
        )
        # A freshly created user is unsuspended, in the target OU, in no groups
        # and holds no licence, so the rest of the plan works from that state.
        current = UserState(email=employee.email, org_unit=employee.org_unit)

    if current.suspended:
        actions.append(
            Action(kind="unsuspend_user", target=employee.email, detail="re-activating returning hire")
        )

    if current.org_unit != employee.org_unit:
        actions.append(
            Action(
                kind="move_user",
                target=employee.email,
                detail=f"{current.org_unit} -> {employee.org_unit}",
                payload={"orgUnitPath": employee.org_unit},
            )
        )

    for group in employee.groups:
        if group not in current.groups:
            actions.append(
                Action(kind="add_to_group", target=group, detail=employee.email, payload={"email": employee.email})
            )

    wanted_sku = employee.license_sku or config.default_license_sku
    if wanted_sku and current.license_sku != wanted_sku:
        actions.append(
            Action(
                kind="assign_license",
                target=employee.email,
                detail=f"{wanted_sku} (was {current.license_sku or 'none'})",
                payload={"skuId": wanted_sku},
            )
        )

    return actions


def _plan_leaver(employee: Employee, current: UserState | None, config: Config) -> list[Action]:
    if current is None:
        return []

    actions: list[Action] = []

    # Suspend first. Everything after this is housekeeping; if the run dies
    # halfway, the account is already unable to sign in.
    if not current.suspended:
        actions.append(
            Action(kind="suspend_user", target=employee.email, detail="offboarding: block sign-in first")
        )

    if current.org_unit != config.leavers_ou:
        actions.append(
            Action(
                kind="move_user",
                target=employee.email,
                detail=f"{current.org_unit} -> {config.leavers_ou}",
                payload={"orgUnitPath": config.leavers_ou},
            )
        )

    for group in sorted(current.groups):
        actions.append(
            Action(kind="remove_from_group", target=group, detail=employee.email, payload={"email": employee.email})
        )

    # Licences are intentionally NOT reclaimed here. The seat should stay
    # attached until Drive ownership is transferred and any legal hold is
    # confirmed — reclaiming early destroys exactly the data an audit asks for.
    return actions


def summarise(actions: Iterable[Action]) -> str:
    """Human-readable plan, one action per line, with a count per kind."""
    actions = list(actions)
    if not actions:
        return "No changes required — directory already matches HR."
    lines = [a.describe() for a in actions]
    counts: dict[str, int] = {}
    for action in actions:
        counts[action.kind] = counts.get(action.kind, 0) + 1
    tally = ", ".join(f"{kind}={n}" for kind, n in sorted(counts.items()))
    lines.append("")
    lines.append(f"{len(actions)} action(s): {tally}")
    return "\n".join(lines)
