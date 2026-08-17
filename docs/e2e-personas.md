# E2E personas & fixtures

Aligned with [role-architecture.md](./role-architecture.md): **Role** = access, **Grade** = authority, **Designation** = title.

## Passwords

| OK | Not OK |
|----|--------|
| `e2e/.env` (gitignored) | Committing `.env` |
| Shared `E2E_PASSWORD` for `e2e.*` users | Using these on production |

Default shared password: `E2eTestPass!26`. Admin: `password` (override in `.env`).

## Seed

```bash
E2E_PASSWORD='E2eTestPass!26' bench --site sevamrita.local execute volunteering.volunteering.e2e_seed.seed_e2e_personas
```

Chain: `employee / employee_b / associate / unpaid → manager → director → chair`

| Alias | Email | Roles | Grade | Designation |
|-------|-------|-------|-------|-------------|
| employee | e2e.employee@sevamrita.local | Employee | Associate | Program Officer |
| employee_b | e2e.employee.b@sevamrita.local | Employee | Associate | Program Officer |
| associate | e2e.associate@sevamrita.local | Employee | Associate | Associate |
| manager | e2e.manager@sevamrita.local | Employee, Leave Approver, Expense Approver | Manager | Operations Manager |
| director | e2e.director@sevamrita.local | Employee, Leave Approver, Expense Approver | Director | Director |
| chair | e2e.chair@sevamrita.local | Employee, Accounts User | **Board of Directors** | Chairperson |
| hr | e2e.hr@sevamrita.local | HR Manager, Employee | Manager | HR Manager |
| accounts | e2e.accounts@sevamrita.local | Accounts Manager, Accounts User, Employee | Manager | Accounts Manager |
| unpaid | e2e.unpaid@sevamrita.local | Employee | Associate | Volunteer Staff |
| coordinator | e2e.coordinator@sevamrita.local | NGO Coordinator, Employee | Manager | NGO Coordinator |
| volunteer | e2e.volunteer@sevamrita.local | NGO Member only | — (no Employee) | — |
| admin | Administrator | existing | — | — |

Manager is `department_head` of **E2E Operations**. Obsolete Board *roles* are not assigned (authority is Grade).

## Use in specs

```ts
import { personaStorage } from '../helpers/personas';

test.describe('as employee', () => {
  test.use({ storageState: personaStorage('employee') });
  test('…', async ({ page }) => {});
});
```

## Levels

| Tag | Meaning |
|-----|---------|
| `@smoke` | L1 load / session |
| `@regression` | L2 happy path |
| `@critical` | L3 P0 / multi-actor |
