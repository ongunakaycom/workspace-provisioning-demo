<div align="center">

# ☁️ Cloud-Native Workspace Provisioning & IAM Automation

[![CI](https://github.com/ongunakaycom/workspace-provisioning-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/ongunakaycom/workspace-provisioning-demo/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Google Workspace](https://img.shields.io/badge/Google_Workspace-Admin_SDK-4285F4?logo=google&logoColor=white)](https://developers.google.com/admin-sdk)
[![Dependencies](https://img.shields.io/badge/Dependencies-Zero-brightgreen.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Idempotent Joiner-Mover-Leaver (JML) automation for Google Workspace.**  
*Reconcile HR truth with directory state — purely, safely, and without credentials.*

A production-grade Python engine demonstrating **Infrastructure-as-Code principles applied to Identity & Access Management (IAM)**.  
This repository serves as a comprehensive hands-on lab for Platform Engineering, Identity Automation, and Zero-Trust Provisioning.

</div>

---

## 🏛️ Architecture & Workflow

```text
[ HR Truth (CSV) ] ──┐
                     │
[ Directory Snapshot ] ──► [ build_plan() ] ──► [ Action List ] ──┬─► [ print() ] (Dry-Run)
                     │      (Pure Function)                       │
[ Config Policy ] ───┘                                            └─► [ execute() ] (Apply)
                                                                        │
                                                                        ▼
                                                              [ Google Admin SDK ]
                                                              (Fake or Real Tenant)
                                                                        │
                                                                        ▼
                                                              [ Idempotent State ]
```

**Engineering Principle:** The planner (`build_plan`) is a **pure function** — zero network calls, zero side effects. It calculates the exact diff between desired state (HR) and actual state (Directory). The executor (`execute`) is the *only* component that mutates state, and it only runs when explicitly invoked via `--apply`.

---

## 🛠️ Tech Stack & Engineering Decisions

| Layer | Technology | Engineering Decision |
|-------|------------|----------------------|
| **Application** | Python 3.11+ | Zero external dependencies. Stdlib only. |
| **Testing** | `unittest` | 26 tests. 100% offline. No credentials required. |
| **CI (Integration)** | GitHub Actions | Automated tests on every push/PR. Matrix: Python 3.11 & 3.12. |
| **API Layer** | Google Admin SDK | Resilient execution with `429` and `5xx` retry logic. |
| **Safety Gate** | `--apply` flag | Dry-run by default. Mutations require explicit intent. |
| **Policy Engine** | `Config.allowed_ous` | Fail-fast OU allowlist. Prevents silent policy dead zones. |
| **Alt. Runtime** | Google Apps Script | Lightweight variant for ad-hoc admin execution via Sheets. |

---

## 📂 Repository Structure

```text
.
├── .github/workflows/ci.yml       # CI: Matrix testing, offline verification
├── apps_script/                   # Google Apps Script variant (Code.gs)
├── data/                          # Example HR CSVs & directory snapshots
├── docs/                          # Architecture & onboarding documentation
├── provisioner/                   # Core Logic
│   ├── models.py                  # Domain models (Employee, UserState, Action, Config)
│   ├── plan.py                    # The Pure Planner (build_plan)
│   ├── directory.py               # API abstraction (FakeDirectory, GoogleDirectory)
│   └── cli.py                     # CLI entry point (dry-run, apply)
├── tests/                         # Unit & E2E tests (offline)
├── .gitignore
├── LICENSE
└── README.md
```

---

## ✅ Verification & CI

This project doesn't claim to be tested; it is **verified on every push**.

### Local Verification
Reproduce the CI environment locally on a bare Python install (no dependencies required):

```bash
$ python -m unittest discover -s tests -t . -v
test_leaver_does_not_revoke_license (tests.test_plan.TestPlan) ... ok
test_typo_in_ou_halts_execution (tests.test_cli.TestCLI) ... ok
test_dry_run_produces_no_side_effects (tests.test_cli.TestCLI) ... ok
...
----------------------------------------------------------------------
Ran 26 tests in 0.042s

OK
```

### Automated CI Pipeline
Every commit to `main` triggers the [![CI](https://github.com/ongunakaycom/workspace-provisioning-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/ongunakaycom/workspace-provisioning-demo/actions/workflows/ci.yml) workflow.  

The pipeline:
1. Provisions a fresh `ubuntu-latest` runner.
2. Tests against **Python 3.11 and 3.12** (via matrix strategy).
3. Executes the full offline test suite.
4. Fails the build if any test fails, preventing broken code from merging.

---

## 🚀 Quick Start (Offline / No Credentials)

```bash
# 1. Run the test suite (26 unit and e2e tests)
python -m unittest discover -s tests -t .

# 2. Execute a dry-run plan against the example data
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

*(Note: Ada Lovelace is in the input and produces 0 actions — because she is already correct. That is the whole point of idempotency.)*

---

## 🔐 Security & Best Practices

*   **Dry-Run by Default:** The CLI requires an explicit `--apply` flag to mutate a live directory. Engineers can review the entire diff before execution.
*   **Fail-Fast OU Allowlist:** An HR typo (`/Enginering`) halts the run with exit code 2. It will never silently create a policy dead zone.
*   **Suspension-First Offboarding:** If a run dies halfway, the account is already blocked from signing in. Remaining steps are housekeeping.
*   **Zero License Reclamation:** Seats stay attached until Drive ownership and Vault holds are confirmed. A test fails if someone tries to add `revoke_license` to the leaver path.
*   **Resilient API Layer:** Exponential backoff for `429` and `5xx` errors. `4xx` errors fail immediately (no noise retries).
*   **Credentials Hygiene:** Production keys (`credentials.json`) are strictly `.gitignore`d. Test suites run entirely offline.

---

## 🗺️ Roadmap (Next Steps)

- [ ] Drive ownership transfer as an explicit step in `_plan_leaver`
- [ ] Vault matter/hold lookup before license reclaim
- [ ] Terraform module for the GCP project and OU skeleton (using the same allowlist paradigm)
- [ ] Structured audit log (one line per action, shipped to BigQuery)
- [ ] Helm chart for deploying the engine as a scheduled K8s CronJob

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