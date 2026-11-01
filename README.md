<div align="center">

# ☁️ Workspace Provisioning Engine — Cloud Engineer Portfolio

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Google Workspace](https://img.shields.io/badge/Google_Workspace-Admin_SDK-4285F4?logo=google&logoColor=white)](https://developers.google.com/admin-sdk)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Tests](https://img.shields.io/badge/Tests-26%20Passing-success.svg)]()
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)]()

An idempotent, dry-run-first Joiner-Mover-Leaver (JML) engine for Google Workspace.
*Reconcile HR truth with directory state — safely, purely, and without credentials.*

</div>

---

## 🎯 Executive Summary

A production-grade demonstration of **Infrastructure-as-Code principles applied to Identity & Access Management (IAM)**. The goal: replace brittle, one-off provisioning scripts with a pure, testable, and fully idempotent reconciliation engine that treats Google Workspace like a declarative state machine.

**Key Achievements:**
- 🧠 **Pure Planner** — `build_plan()` has zero side effects, zero network calls, and 100% unit-testable logic.
- 🔁 **Strict Idempotency** — Running twice yields the same plan; running against an applied state yields zero actions.
- 🛡 **Safety by Default** — Dry-run is the default. Production mutations require an explicit `--apply` flag.
- 🧪 **Offline Testing** — 26 end-to-end and unit tests pass on a bare Python 3.11+ install with no external dependencies.
- ⚡ **Resilient API Layer** — Exponential backoff with `Retry-After` support for Google’s aggressive 429 rate limits.

---

## 🏗 Architecture

```text
┌────────────────────────────────────────────────────────┐
│                 HR Truth (CSV)                         │
│            data/new_hires.example.csv                  │
└──────────────────────────┬─────────────────────────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
     ┌──────▼──────┐               ┌──────▼──────┐
     │ load_employees│             │  Snapshot   │
     │  (pure)      │             │ (JSON/API)  │
     └──────┬──────┘               └──────┬──────┘
            │                             │
            └──────────────┬──────────────┘
                           │
                ┌──────────▼──────────┐
                │    build_plan()     │
                │  (Pure Function)    │
                └──────────┬──────────┘
                           │
                ┌──────────▼──────────┐
                │   [Action] List     │
                │  (Diff / Dry-Run)   │
                └──────────┬──────────┘
                           │
            ┌──────────────┴──────────────┐
            │                             │
     ┌──────▼──────┐               ┌──────▼──────┐
     │  print()    │               │  execute()  │
     │  (Dry-Run)  │               │  (--apply)  │
     └─────────────┘               └──────┬──────┘
                                          │
                               ┌──────────▼──────────┐
                               │   Google Admin SDK  │
                               │   (Fake or Real)    │
                               └─────────────────────┘
```

**Engineering Decision:** The planner is separated from the executor. `build_plan()` is a pure function that takes HR data and a directory snapshot and returns a list of actions. This means you can review the entire diff before anything is written, and you can test every branch of the decision logic without mocking a single API.

---

## ⚙️ Tech Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| **Language** | Python 3.11+ | Zero dependencies, stdlib only. |
| **Planner** | Pure functions | Deterministic, side-effect-free, fully testable. |
| **Directory API** | Google Admin SDK | Real tenant execution with retry/backoff. |
| **Testing** | `unittest` | 26 tests, offline, no credentials required. |
| **CLI** | `argparse` | Explicit `--apply` gate for production safety. |
| **Alt. Runtime** | Apps Script | Lightweight variant for one-off Sheet-based runs. |

---

## 🧠 Engineering Highlights

### 1. Plan and Apply Are Separate
`build_plan(employees, snapshot, config)` is a pure function. No network, no Google imports, no side effects. You can read the entire diff before anything is written, and you can test every branch of the decision logic cheaply.

### 2. Every Action Is Idempotent
Actions are derived from the difference between HR and the current directory, never from a script that assumes it is the first run. Running twice produces the same plan; running against the post-apply state produces an empty one.

### 3. Fail-Fast on Typos
`Config.allowed_ous` is an allowlist. A child OU is only allowed when one of its parents is. An HR export with `/Enginering` stops the run with exit code 2 instead of quietly creating a policy dead zone.

### 4. Suspension First on Offboarding
If the run dies halfway, the account is already unable to sign in. The remaining steps are housekeeping. Ordering is asserted in tests, not commented.

### 5. Zero License Reclamation
The seat stays attached until Drive ownership is transferred and any legal hold is confirmed. A test fails if someone adds a `revoke_license` action to the leaver path.

---

## 🚀 Quick Start (Offline / No Credentials)

```bash
# Run the test suite (26 unit and e2e tests)
python -m unittest discover -s tests -t .

# Execute a dry-run plan
python -m provisioner.cli --input data/new_hires.example.csv \
    --snapshot data/snapshot.example.json
```

**Sample Dry-Run Output:**
```text
add_to_group    eng-core                           grace.hopper@example.com
assign_license  grace.hopper@example.com           Google-Apps-For-Business (was none)
create_user     tim.berners@example.com            Tim Berners -> /Engineering
...
11 action(s): add_to_group=3, assign_license=2, create_user=1, move_user=1,
remove_from_group=2, suspend_user=1, unsuspend_user=1
```

*Ada Lovelace is in the input and produces no actions — because she is already correct. That is the whole point of the design.*

---

## 📦 Production Deployment

Running against a live tenant requires a Super Admin and a service account.

1. Enable **domain-wide delegation** for a service account and impersonate a super admin.
2. Grant scopes: `admin.directory.user`, `admin.directory.group.member`, `apps.licensing`.
3. Save the key as `credentials.json` — it is git-ignored, and it must stay that way.
4. Start with `--fake --apply` against a snapshot from production, then compare results before touching the real directory.

---

## 📋 Scope & Limitations

This engine is intentionally scoped to solve the JML problem precisely:
- **No Drive transfer / Vault hold** — these are policy decisions, not script defaults.
- **No Terraform for GCP** — project structure is a separate state file.
- **No nested groups** — `add_to_group` is flat membership.
- **Not battle-tested at 1,500+ users** — it runs on an example snapshot and a fake directory.

## 🗺 Roadmap
- [ ] Drive ownership transfer as an explicit step in `_plan_leaver`
- [ ] Vault matter/hold lookup before license reclaim
- [ ] Terraform module for GCP project/OU skeleton with the same allowlist idea
- [ ] Structured audit log (one line per action, shipped to BigQuery)

---

## 📜 Apps Script Variant

`apps_script/Code.gs` is the same idea for the case where an admin should be able to run it from a Sheet without a deployment pipeline — smaller, with a `DRY_RUN` constant at the top and a log sheet. Python for anything on a schedule or in CI; Apps Script for the one-off a hiring manager asks for on a Friday afternoon.

---

## 👤 Author

<div align="center">

**Ongun Akay** — Cloud Engineer
*Google Cloud · AI/LLM · GKE & Cloud Run*

[![Website](https://img.shields.io/badge/Website-ongunakay.com-000000?style=flat-square&logo=google-chrome)](https://ongunakay.com)
[![GitHub](https://img.shields.io/badge/GitHub-ongunakaycom-181717?style=flat-square&logo=github)](https://github.com/ongunakaycom)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-ongunakay-0A66C2?style=flat-square&logo=linkedin)](https://linkedin.com/in/ongunakay)
[![Email](https://img.shields.io/badge/Email-info@ongunakay.com-EA4335?style=flat-square&logo=gmail)](mailto:info@ongunakay.com)

</div>

---

## 📄 License

MIT — see [LICENSE](./LICENSE).