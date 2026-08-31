# Volunteering E2E (Playwright)

Browser-first Desk / SPA tests. Levels: **@smoke** (L1), **@regression** (L2), **@critical** (L3).
Modules: **@accounts** **@hr** **@volunteering** **@ops**. Tag **@ui** marks specs that drive Frappe Desk forms (not RPC shortcuts).

## Two-layer model

| Layer | How | Used for |
|-------|-----|----------|
| **UI** (`@ui`) | Playwright `page` + Desk page objects in `e2e/pages/desk/` | Create/submit/approve, `msgprint`/`confirm`, workflow buttons |
| **API setup** | `e2eCall` on `volunteering.volunteering.e2e_api` | Seed, cleanup, `trigger_attendance_job`, `set_advance_settlement`, post-action DB asserts |

`e2eCall` uses `fetch` with the target persona’s saved cookies (not the test page’s `storageState`). Stale sessions are refreshed automatically via `/api/method/login`.

User-facing actions (`create_dwl`, `workflow_action`, etc.) are **blocked** in `e2e_api.py` — specs must use the browser.

Desk helpers: `e2e/helpers/desk.ts`, `e2e/helpers/dialogs.ts`, `e2e/helpers/persona-context.ts` (`withPersona` for multi-actor flows).

Expect full `@regression` suite runtime **~45–90 minutes** (headed may be slower). Use module filters while iterating.

## Prerequisites

1. `bench start` — site at `http://sevamrita.local:8000`
2. Install browsers **once** into the user cache (Playwright will skip if they are already there):

```bash
cd apps/volunteering
yarn install
PLAYWRIGHT_BROWSERS_PATH="$HOME/Library/Caches/ms-playwright" npx playwright install chromium
cp e2e/.env.example e2e/.env   # if needed
```

Do not run `playwright install` before every test run. The config remaps Cursor’s throwaway sandbox cache to `$HOME/Library/Caches/ms-playwright`.

3. Seed grade-based personas (role-architecture aligned):

```bash
E2E_PASSWORD='E2eTestPass!26' bench --site sevamrita.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas
```

## Scripts

| Command | Purpose |
|---------|---------|
| `yarn test:e2e:smoke` | L1 — hubs, login, ping |
| `yarn test:e2e:regression` | L2 — happy paths |
| `yarn test:e2e:critical` | L3 — full P0 / multi-actor |
| `yarn test:e2e:hr` / `:accounts` / `:volunteering` / `:ops` | Module filter |
| `yarn test:e2e:last-failed` | Re-run only tests that failed last time (`test-results/.last-run.json`) |
| `yarn test:e2e:ui` | Interactive UI Mode |
| `yarn test:e2e:ui-only` | Only `@ui` tagged specs |

## Layout

Specs live in `e2e/tests/{accounts,hr,volunteering,ops,cross-module,shared}/*.spec.ts`. Tags: `@smoke`, `@regression`, `@critical`, `@ui`.

Personas: [e2e-personas.md](./e2e-personas.md). Coverage: [e2e-coverage.md](./e2e-coverage.md).
Git rules: [e2e-git.md](./e2e-git.md). Docs map: [README.md](./README.md).

## Manager float (`manager-float.spec.ts`)

| ID | Layer | Notes |
|----|-------|-------|
| AC-MFL-001, AC-MFL-002 | API fixtures | `seedManagerFloatClaim` + `seedApproveExpenseClaim`; asserts firm vs manager-float settlement |
| AC-MFL-003 | Desk UI | Manager persona; `expectEscalateVisible` waits for `get_approver_action_flags` then **Review** menu |
| AC-MFL-004, AC-MFL-005 | Advance Portal | Employee/manager `storageState`; team row scoped via `AdvancesPage.teamFloatRequestRow()` |

Fixtures: `e2e/helpers/manager-float-fixtures.ts`. Product settlement runs on **Approve → submit** (`settle_manager_float_expense_claim_on_submit`), after HRMS resets `total_amount_reimbursed`.

**Parallel runs:** see [e2e-parallel.md](./e2e-parallel.md) (multi-site recommended; default remains `workers: 1`).
