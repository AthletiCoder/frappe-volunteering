# Volunteering

ERPNext app for NGO day-to-day work: volunteer events, staff attendance and leave, and controlled spending (advances, claims, vendor payments, and project budgets).

**In the product, start here:** [Home](/volunteering/home) · [Help](/help)

---

## For staff (employees)

Use Desk search (`Ctrl` / `Cmd` + `K`) or the hubs above. In-app help is the live guide after migrate.

| I want to… | Open |
|---|---|
| Log work, leave, WFH, attendance | [Home](/volunteering/home) · [HR help](/help/hr/home) |
| Request an advance or claim money back | [Home](/volunteering/home) · [Advance Portal](/volunteering/advances) |
| See how to spend (vendor vs advance vs claim) | [How to spend](/help/accounts/how-to-spend) · [docs/how_to_spend.md](docs/how_to_spend.md) |
| Check project budget | [Budget Health](/volunteering/budget-health) |
| HR details (work log, leave, WFH) | [docs/hr_hrms_guide.md](docs/hr_hrms_guide.md) |

**Advances vs projects:** do not tag an **Employee Advance** to a project — it is cash in your hands. When you settle, the **Expense Claim must have a Project** so department budget and approvals apply. Purchase Orders also require a Project. Purchase Invoices follow the approved PO (they do not double-count budget).

Approvals follow **Reports To** and **Employee Grade** limits. Accounts pays after approval; they do not replace your manager on day-to-day spend.

---

## For operators (Accounts / HR / admin)

1. Set each employee’s **Reports To** and **Grade** (and Designation as the job title).
2. Open **Approval & Advance Limits** and confirm amounts (or Reset to Defaults).
3. On each **Project**, set **Department Budgets** and a **Cost Center**.
4. Optional: [Daily Work Log Settings](docs/hr_hrms_guide.md) for the summary email.
5. After install or upgrade: `bench migrate`, then build the SPA once:

```bash
cd apps/volunteering/frontend
yarn install && yarn build
```

More: [Tally → ERPNext](docs/tally_to_erpnext_accounts_guide.md) · [Cashfree / disbursement](docs/fund_disbursement_ops_checklist.md) · [Role architecture](docs/role-architecture.md)

---

## For developers

| Topic | Doc |
|---|---|
| Docs map | [docs/README.md](docs/README.md) |
| Playwright E2E | [docs/e2e.md](docs/e2e.md) · [coverage](docs/e2e-coverage.md) · [personas](docs/e2e-personas.md) |
| Frontend (Budget Health, Advance Portal) | [frontend/README.md](frontend/README.md) |
| Local log / env | [docs/developer_log_env.md](docs/developer_log_env.md) |
| Historical sprint notes | [DEVELOPMENT_PLAN.md](DEVELOPMENT_PLAN.md) |

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch version-16
bench install-app volunteering
```

```bash
cd apps/volunteering
pre-commit install   # ruff, eslint, prettier, pyupgrade
yarn test:e2e:smoke
```

Site for local E2E: `http://sevamrita.local:8000`. Do not commit `e2e/.env` or `e2e/.auth/`.

---

## License

MIT
