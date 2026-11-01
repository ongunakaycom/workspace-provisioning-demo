# Architecture Decision Records (ADR)

Short notes on the choices that are not obvious from the code, and what was given up to make them.

---

## ADR 001: Plan first, write second

`build_plan` is a pure function over (HR rows, directory snapshot, config). It imports nothing from Google, opens no sockets, and returns a list of plain `Action` objects.

**Why:** Provisioning bugs are cheap to find in a diff and expensive to find in a directory. Separating the decision from the write means the decision can be read by someone else before it happens, and tested exhaustively in milliseconds.

**Cost:** Two passes over the data, and a snapshot that can go stale between plan and apply. For a tenant of this size the window is seconds and the operation is idempotent, so a stale snapshot produces a smaller plan, never a wrong one.

---

## ADR 002: Idempotency over transactions

Every action is derived from the *difference* between HR and the current directory. Nothing assumes it is the first run.

**Why:** Half-finished onboarding runs are the normal case, not the exception — an API dies, someone closes a laptop, a quota is hit. A script that has to be run exactly once is a script that will be run wrong.

**Tested:** Applying the plan and re-planning yields zero actions (`test_cli.py::test_apply_then_replan_is_a_no_op`).

---

## ADR 003: An OU allowlist, not a free-form path

`Config.allowed_ous` is checked before any action is planned, and a child path is allowed only if one of its parents is listed.

**Why:** `orgUnitPath` is a string that creates what it names. A typo in an HR export does not fail — it silently creates `/Enginering`, and everyone in it inherits root-level policies. That is a security incident that takes months to notice.

**Cost:** Adding a legitimately new top-level OU needs a config change and a review. That is the point.

---

## ADR 004: Suspension before everything on offboarding

The leaver plan always suspends first, then moves, then removes group memberships.

**Why:** If the run stops after action one, the account cannot sign in. If the order were reversed, a partial run would leave an active account with no groups and no owner paying attention to it.

---

## ADR 005: Licences are not reclaimed automatically

Offboarding never revokes a licence seat.

**Why:** The seat is attached to the Drive and the mailbox. Reclaiming it before ownership transfer destroys the data an audit or a legal hold will ask for, and it does so irreversibly. Licence reclamation is a policy decision with a human owner, not a default a script should pick.

**Tested:** `test_plan.py::test_licence_is_never_reclaimed_on_offboarding` fails if anyone adds a revoke action to the leaver path.

---

## ADR 006: Retry 429 and 5xx, nothing else

`call_with_retry` retries quota and server errors with exponential backoff, honours `Retry-After`, and re-raises everything else immediately.

**Why:** A bulk onboarding run is exactly the burst that triggers Directory API rate limits, so no retry means a guaranteed partial failure. But retrying a `400` is worse than failing: it hides a malformed request behind five identical errors.

---

## ADR 007: Python for automation, Apps Script for the one-off

`apps_script/Code.gs` duplicates the planning logic in a smaller form.

**Why:** The two audiences are different. Scheduled or CI-driven reconciliation needs tests, version control, and a real language; the ad-hoc request from a hiring manager on a Friday needs a button in a Sheet. Pretending one tool covers both produces a 600-line Apps Script nobody dares edit.

**Cost:** The logic exists twice, and the two can drift. If this were production I would generate the Sheet version from a shared spec, or accept that the Apps Script one stays deliberately dumber — which is what it is now.