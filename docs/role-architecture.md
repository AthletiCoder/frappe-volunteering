# Role, Designation, and Grade architecture

How Sevamrita Volunteering assigns access and approval authority on ERPNext / HRMS.

## Three axes (do not conflate)

| Axis | Where | Purpose | Examples |
|------|--------|---------|----------|
| **Role** | User → Roles / Role Profiles | Module access (DocPerm, workspaces) | `Employee`, `HR Manager`, `Accounts User`, `NGO Coordinator` |
| **Designation** | `Employee.designation` | Job title / position label | Program Officer, Chairperson, Operations Manager |
| **Grade** | `Employee.grade` → Employee Grade | Seniority band (pay-ready + approve band) | Associate, Manager, Director, Board of Directors |
| **Limits** | **Approval and Advance Limits** (Setup) | How much a Grade may approve / advance | Child rows keyed by Grade |
| **Chain** | `reports_to`, `leave_approver` | Who is next in line | Manager’s Employee |
| **Dept head** | `Department.department_head` | Dept-scoped expense visibility | User on Department master |

Stock ERPNext keeps monetary policy on a Setup DocType (Authorization Rule pattern), not on Designation/Grade masters. We follow that: amounts live only on **Approval and Advance Limits**.

## Custom volunteering roles (keep)

| Role | Scope |
|------|--------|
| `NGO Member` | Volunteer self-service only. **Never** assign to paid staff. |
| `NGO Coordinator` | Org-wide volunteering ops |
| `NGO Admin` | Volunteering masters (delete, rating override) |

## Core roles we use

| Role | Scope |
|------|--------|
| `Employee` | Staff desk baseline |
| `Leave Approver` / `Expense Approver` | Approver inbox DocPerm (auto-granted when someone is an approver) |
| `HR User` / `HR Manager` | People ops |
| `Accounts User` / `Accounts Manager` / `Auditor` | Books and payments |
| `System Manager` | Tech break-glass only |

## Obsolete (do not assign)

These are removed / migrated away — authority is Grade + Employee fields:

- `Executive Board Member`, `Executive Board Chairperson`
- `NGO Board Member`, `NGO Board Chairperson`
- `NGO Department Head` → use `Department.department_head`

### Migration status

`volunteering.patches.migrate_authority_to_grade` copies authority onto
`Employee.grade` and leaves the roles in place; `volunteering/authority.py` still
accepts them as a fallback. Enable
`volunteering.patches.remove_obsolete_board_roles` in `patches.txt` to delete the
roles, after which grade and `department_head` are the only sources of authority.

The limits child table keeps the fieldname `designation` (to avoid a DB rename);
its values are Employee Grades and the field is labelled **Grade**.

## Seeded Grades (approve / self-advance defaults)

| Grade | Max approve (others) | Max self advance |
|-------|----------------------|------------------|
| Associate | 0 | 2,000 |
| Manager | 2,000 | 5,000 |
| Vice President | 5,000 | 10,000 |
| President | 10,000 | 15,000 |
| Director | 25,000 | 50,000 |
| CEO | 50,000 | 50,000 |
| Executive Board | 100,000 | 100,000 |
| Board of Directors | Unlimited | — |

Board of Directors also gates: create-block for EC/PO/EA, budget hard-override, leave > 7 days, digests, fallback approver, and workflow override Approve/Reject.

## Onboarding checklist

1. Create **User** + **Employee** (link `user_id`)
2. Set **Designation** = job title
3. Set **Grade** = seniority / approval band
4. Set **Reports To** = manager (leave approver syncs from this)
5. Assign **Roles** / Role Profile for modules they need
6. If they head a department → set **Department.department_head**
7. Never give paid staff `NGO Member`; never use Board* User Roles

### Examples

- Line manager: Roles `Employee` + `Leave Approver`; Grade `Manager`; Designation e.g. Operations Manager  
- Board chair helping Accounts: Roles `Employee` + `Accounts User`; Grade `Board of Directors`; Designation e.g. Chairperson  
- Volunteer: Role `NGO Member` only (no Employee required)

## People rules

- Paid staff are never on-ground volunteers (`NGO Member`).
- Board members may also hold staff function roles in a small NGO.
- Soft segregation of duties only (document preferred combos; not hard-enforced).
