# Volunteering E2E (Playwright)

Browser / API / ops tests. Levels: **@smoke** (L1), **@regression** (L2), **@critical** (L3).
Modules: **@accounts** **@hr** **@volunteering** **@ops**.

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
| `yarn test:e2e:headed` | Visible browser |

## Layout

```
e2e/tests/
  auth.setup.ts
  accounts|hr|volunteering|ops/
    smoke.spec.ts
    regression/   # L2
    critical/     # L3
  shared/persona-smoke.spec.ts
```

Personas: [e2e-personas.md](./e2e-personas.md). Coverage: [e2e-coverage.md](./e2e-coverage.md).
Git rules: [e2e-git.md](./e2e-git.md).
