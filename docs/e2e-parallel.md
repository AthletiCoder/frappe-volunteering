# Parallel E2E runs

The default suite is **serial** (`workers: 1`, `fullyParallel: false`) because specs share one site DB, personas, and `_E2E Test Project`. Running many Playwright workers on **one site** causes fixture races — not useful concurrency testing.

## Recommended on M5 Mac Air (16 GB)

| Setup | Sites | Workers/site | Use |
|-------|------:|-------------:|-----|
| **Start here** | 2 | 1 | HR on `:8000`, Accounts on `:8001` |
| Moderate | 3 | 1 | + Volunteering/ops on `:8002` |
| Avoid | 4+ | 2+ | Swap / thermal throttling |

One MariaDB + one Redis; add **sites** on different ports, not duplicate benches.

## Env vars

| Variable | Default | Purpose |
|----------|---------|---------|
| `BASE_URL` | `http://sevamrita.local:8000` | Target site |
| `E2E_AUTH_DIR` | `e2e/.auth` | Isolated Playwright cookies per site/shard |
| `PW_WORKERS` | `1` | Playwright workers (keep `1` per site until fixtures are partitioned) |
| `E2E_FORCE_AUTH` | — | Re-login all personas in `auth.setup` |

## Yarn scripts (after second site exists)

```bash
# Terminal 1 — primary site + HR
yarn test:e2e:parallel:hr

# Terminal 2 — second site + Accounts (set BASE_URL_ACCOUNTS in e2e/.env)
yarn test:e2e:parallel:accounts
```

Each script uses its own `E2E_AUTH_DIR` so parallel runs do not overwrite cookies.

## Playwright sharding (same site — flaky today)

```bash
SHARD=1 TOTAL=2 yarn test:e2e:shard
SHARD=2 TOTAL=2 yarn test:e2e:shard
```

Only safe once specs use worker-scoped projects/employees. Not recommended for the full suite yet.

## Second site (bench — needs explicit approval)

```bash
bench new-site sevamrita-e2e-2.local --admin-password password
bench --site sevamrita-e2e-2.local install-app erpnext hrms volunteering
bench --site sevamrita-e2e-2.local migrate

E2E_PASSWORD='E2eTestPass!26' bench --site sevamrita-e2e-2.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas

bench --site sevamrita-e2e-2.local serve --port 8001
```

Add to `/etc/hosts` if using `.local` hostnames. Point `BASE_URL_ACCOUNTS` at the new port.

## Shared-DB collision points

Parallel specs on **one** site still fight over:

- `_E2E Test Project` (PROJ-0003)
- `e2e.employee` / `e2e.manager` cast
- `cleanup_expense_claims_for_project`, `set_employee_reports_to`
- leave allocations, attendance job side effects

Multi-site parallelism avoids most of this; within-site parallelism needs `E2E_WORKER_INDEX` in fixture names (future work).
