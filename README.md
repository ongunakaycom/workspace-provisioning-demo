# Workspace provisioning demo

Reconcile a Google Workspace directory with HR truth: create joiners, move people
between org units, add and remove group memberships, assign licences, and suspend
leavers — idempotently, and with a dry run that is the default.

Runs and tests **without a tenant and without credentials**. 26 unit and
end-to-end tests pass on a bare Python 3.11+ install with no dependencies.

```bash
python -m unittest discover -s tests -t .
```

```bash
python -m provisioner.cli --input data/new_hires.example.csv \
    --snapshot data/snapshot.example.json
```

```
add_to_group    eng-core                           grace.hopper@example.com
assign_license  grace.hopper@example.com           Google-Apps-For-Business (was none)
create_user     tim.berners@example.com            Tim Berners -> /Engineering
add_to_group    eng-core                           tim.berners@example.com
add_to_group    new-hires                          tim.berners@example.com
assign_license  tim.berners@example.com            Google-Apps-For-Business (was none)
unsuspend_user  alan.turing@example.com            re-activating returning hire
suspend_user    katherine.johnson@example.com      offboarding: block sign-in first
move_user       katherine.johnson@example.com      /Operations -> /Leavers
remove_from_group data-team                        katherine.johnson@example.com
remove_from_group ops-oncall                       katherine.johnson@example.com

11 action(s): add_to_group=3, assign_license=2, create_user=1, move_user=1,
remove_from_group=2, suspend_user=1, unsuspend_user=1
```

Ada Lovelace is in the input and produces no actions, because she is already
correct. That is the whole point of the design.

## The two properties that matter

**1. Plan and apply are separate.** `build_plan(employees, snapshot, config)` is a
pure function: no network, no Google imports, no side effects. You can read the
entire diff before anything is written, and you can test every branch of the
decision logic cheaply. Writing is a separate loop over the resulting actions.

**2. Every action is idempotent.** Actions are derived from the difference between
HR and the current directory, never from a script that assumes it is the first run.
Running twice produces the same plan; running against the post-apply state produces
an empty one. The CLI proves this on every `--apply` instead of claiming it:

```
applied 11 action(s); second pass: 0 remaining
```

## Architecture

```
data/new_hires.csv ──┐
                     ├─► load_employees ─┐
directory snapshot ──┘                   ├─► build_plan ─► [Action] ─┬─► print (dry run)
                                         │                           └─► execute ─► Directory
config (allowed OUs, ────────────────────┘
        domains, leaver OU)
```

| Module | Responsibility |
|---|---|
| `provisioner/models.py` | `Employee`, `UserState`, `Action`, `Config`. Policy lives in `Config.check`. |
| `provisioner/plan.py` | The pure planner. The only place that decides *what* should happen. |
| `provisioner/directory.py` | `call_with_retry`, `FakeDirectory` (offline), `GoogleDirectory` (Admin SDK). |
| `provisioner/cli.py` | CSV input, snapshot loading, dry run, apply. |

## Three decisions worth defending

**A typo must not create an OU.** `Config.allowed_ous` is an allowlist, and a child
OU is only allowed when one of its parents is. An HR export with `/Enginering`
stops the run with exit code 2 instead of quietly creating a policy dead zone that
nobody notices for six months. Tested in `test_plan.py` and `test_cli.py`.

**Suspension comes first on offboarding.** If the run dies halfway, the account is
already unable to sign in; the remaining steps are housekeeping. Ordering is
asserted, not commented.

**Licences are never reclaimed during offboarding.** The seat stays attached until
Drive ownership is transferred and any legal hold is confirmed. Reclaiming it early
is how a company destroys exactly the data an audit will ask for. There is a test
that fails if someone adds a `revoke_license` action to the leaver path.

## Retries

Google's Directory API answers a burst of writes with `429`s, and bulk onboarding is
exactly that burst. `call_with_retry` retries `429` and `5xx` with exponential
backoff, honours `Retry-After` when the API sends it, and re-raises everything else
immediately — a `400` means the request is wrong and retrying it is just noise.

## Running against a real tenant

Not done in this repo, deliberately — it needs a tenant, a super admin and a
service account, none of which belong in a demo.

1. Enable domain-wide delegation for a service account and impersonate a super admin.
2. Grant the scopes in `directory.py` (`admin.directory.user`,
   `admin.directory.group.member`, `apps.licensing`).
3. Save the key as `credentials.json` — it is git-ignored, and it must stay that way.
4. Start with `--fake --apply` against a snapshot taken from production, then compare
   the result with what you expected before touching the real directory.

## What this is not

- **Not battle-tested at scale.** It runs on an example snapshot and a fake directory.
  I have not run it against a 1,500-person tenant, and I would not claim otherwise.
- **No Drive transfer, no Vault hold check.** Offboarding stops at suspension and
  group removal because the steps after that are policy decisions for the business,
  not defaults a script should pick.
- **No Terraform for GCP.** Project structure and org policies are a separate problem
  and deserve their own state file, not a side effect of user provisioning.
- **No group nesting or dynamic groups.** `add_to_group` is flat membership.

## Next

- Drive ownership transfer as an explicit, reviewed step in `_plan_leaver`
- Vault matter/hold lookup before licence reclaim, so the two are never out of order
- Terraform module for the GCP project and OU skeleton, with the same allowlist idea
- Structured audit log (one line per action, shipped to BigQuery) instead of stdout

## Apps Script version

`apps_script/Code.gs` is the same idea for the case where an admin should be able to
run it from a Sheet without a deployment pipeline — smaller, with a `DRY_RUN`
constant at the top and a log sheet. Python for anything on a schedule or in CI,
Apps Script for the one-off a hiring manager asks for on a Friday afternoon.

MIT licensed.
