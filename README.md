<div align="center">

# ☁️ Workspace Provisioning Engine
**Declarative Identity & Access Management (IAM) Automation for Google Workspace**

[![CI](https://github.com/ongunakaycom/workspace-provisioning-demo/actions/workflows/ci.yml/badge.svg)](https://github.com/ongunakaycom/workspace-provisioning-demo/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white)](https://www.python.org)
[![Google Workspace](https://img.shields.io/badge/Google_Workspace-Admin_SDK-4285F4?logo=google&logoColor=white)](https://developers.google.com/admin-sdk)
[![Docker Image](https://img.shields.io/badge/GHCR-Published-blue?logo=docker)](https://github.com/ongunakaycom/workspace-provisioning-demo/pkgs/container/workspace-provisioning-demo)
[![GHCR Published](https://img.shields.io/badge/GHCR-Published-blue?logo=docker)](https://github.com/ongunakaycom/workspace-provisioning-demo/pkgs/container/workspace-provisioning-demo)
[![ADR](https://img.shields.io/badge/Architecture_Decisions-Read_Here-blueviolet?style=flat-square)](./docs/decisions.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

A production-grade, idempotent Joiner-Mover-Leaver (JML) engine designed for high-compliance environments.  
*Reconcile HR truth with directory state — safely, purely, and without credentials.*

</div>

---

## 🎯 Executive Summary

Managing user lifecycles in a financial institution requires strict adherence to compliance and zero-trust principles. This engine applies **Infrastructure-as-Code (IaC) paradigms to IAM**, replacing brittle, imperative provisioning scripts with a purely declarative reconciliation loop.

**Designed for Cloud/DevOps Engineers:**
- 🧠 **Plan/Apply Separation:** A pure, side-effect-free planner (`build_plan`) allows security teams to review the exact execution diff before any state is mutated.
- 🔁 **Strict Idempotency:** State is derived solely from the delta between HR and the directory. Re-running the engine guarantees zero unintended actions.
- 🛡️ **Compliance-First Offboarding:** Leavers are suspended *first*. License reclamation and Drive transfers are intentionally decoupled to prevent data loss and preserve legal holds.
- 🐳 **Hardened Containerization:** Multi-stage Docker builds running as a non-root user, ensuring supply chain and runtime security.

---

## 🏗 Architecture & Data Flow

```text
[ HR System (CSV) ] ──┐
                      ├─► [ load_employees ] ─┐
[ Directory Snapshot ] ┘                      │
                                              ▼
[ Policy Config ] ──────────────────► [ build_plan() ] (Pure Function)
                                              │
                                              ▼
                                     [ [Action] List ] 
                                              │
                      ┌───────────────────────┴───────────────────────┐
                      ▼                                               ▼
               [ print() ]                                     [ execute() ]
            (Dry-Run Default)                                 (--apply Gate)
                                                                      │
                                                                      ▼
                                                          [ Google Admin SDK ]
                                                          (Fake or Real Tenant)
```

---

## 🛡️ Defensible Security & Compliance Decisions

In a fintech environment, a provisioning script is a potential blast radius. This engine mitigates risk through architectural constraints:

1.  **Fail-Fast OU Allowlist:** A typo in an HR export (e.g., `/Enginering`) will halt execution with exit code 2. The engine prevents the silent creation of policy dead zones by enforcing an allowlist of organizational units and their parents.
2.  **Suspension-First Offboarding:** If an offboarding run fails halfway, the identity is already blocked from signing in. Subsequent tasks (group removals) act as housekeeping, ensuring zero unauthorized access windows.
3.  **Zero License Reclamation on Leavers:** The engine *never* automatically revokes licenses during offboarding. Seats remain attached until Drive ownership is explicitly transferred and Vault legal holds are confirmed. (Enforced via automated unit tests).
4.  **Idempotent API Execution:** The Google Admin SDK layer (`call_with_retry`) handles aggressive rate limiting (`429` errors) using exponential backoff, honoring `Retry-After` headers. `4xx` errors fail immediately to prevent noise retries.
5.  **Credential Hygiene:** The CI/CD pipeline operates entirely offline using `FakeDirectory`. Production service account keys (`credentials.json`) are strictly `.gitignore`d.

---

## 🛠 Tech Stack

| Layer | Technology | Rationale |
| :--- | :--- | :--- |
| **Application** | Python 3.11+ | Zero external dependencies. Stdlib only for maximum portability. |
| **Testing** | `unittest` | 26 offline tests (100% branch coverage) ensure logic is robust before hitting a live API. |
| **CI/CD** | GitHub Actions | Matrix testing (Py 3.11/3.12) + automated GHCR Docker publishing. |
| **Security** | CodeQL & Dependabot | Automated vulnerability scanning and dependency updates. |
| **API Layer** | Google Admin SDK | Resilient execution with built-in rate-limit handling. |
| **Alt Runtime** | Google Apps Script | Lightweight variant for ad-hoc admin execution via Sheets. |

---

## 🚀 Quick Start (Offline / No Credentials)

Reproduce the exact CI environment locally on a bare Python install:

```bash
# 1. Run the test suite (26 unit and e2e tests)
python -m unittest discover -s tests -t . -v

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

## 🐳 Container Deployment (GHCR)

This project is continuously built and published to the GitHub Container Registry.

```bash
# Pull the hardened, non-root image
docker pull ghcr.io/ongunakaycom/workspace-provisioning-demo:latest

# Run the dry-run via container
docker run --rm \
  -v $(pwd)/data:/app/data \
  ghcr.io/ongunakaycom/workspace-provisioning-demo:latest \
  --input data/new_hires.example.csv --snapshot data/snapshot.example.json
```

---

## 🗺 Roadmap
- [ ] Integration with HashiCorp Vault for dynamic secret injection.
- [ ] Structured audit logging (JSON) piped directly to Google BigQuery for SIEM ingestion.
- [ ] Terraform module for GCP project and OU skeleton provisioning.
- [ ] Native Slack/Teams webhook integration for `--apply` approval gates.

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

MIT — see [LICENSE](./LICENSE)
