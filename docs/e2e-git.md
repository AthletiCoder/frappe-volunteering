# E2E git versioning rules

## Commit

**Do commit**

- `e2e/tests/**`, `e2e/helpers/**`, `e2e/pages/**`
- `playwright.config.ts`, `e2e/tsconfig.json`, `e2e/.env.example`
- `package.json` / `yarn.lock` (Playwright deps)
- `docs/e2e*.md`, `volunteering/volunteering/e2e_seed.py`

**Never commit**

- `e2e/.env` (passwords)
- `e2e/.auth/` (session cookies)
- `test-results/`, `playwright-report/`, `blob-report/`

These are already in `.gitignore`.

## Branch / PR

- Develop E2E on a feature branch (e.g. `e2e`) → open PR into `main`.
- Prefer one PR for harness+smoke; follow-up PRs for `@regression` / `@critical` suites per module.

## Commit messages

```
test(e2e): add HR L1 smoke for My Work
test(e2e): align personas with grade-based authority
docs(e2e): coverage matrix for spreadsheet P0s
```

No app semver bump for test-only changes unless you explicitly cut a release note.

## After pulling main

1. Re-run seed if `e2e_seed.py` changed:  
   `bench --site sevamrita.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas`
2. Clear stale auth if logins fail: `rm -rf e2e/.auth` then re-run tests (setup recreates sessions).

## Secrets

If `e2e/.env` was ever committed, rotate `E2E_PASSWORD`, re-seed, and purge from git history.
