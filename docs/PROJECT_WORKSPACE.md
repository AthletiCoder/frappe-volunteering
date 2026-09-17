# Governed project workspace

Open `/volunteering/home` and use **Projects and proposals**, **Propose a
project**, or (for managers) **Project approvals**. The Home interface is the
authoritative place to create and change structured projects. The native Desk
Project page remains available for approved details, tasks and milestones, but
project configuration cannot bypass the proposal workflow.

## Roles and record scope

| Role | Approved projects | Proposals | Configuration authority |
| --- | --- | --- | --- |
| Project Proposer | Own proposals and projects they own/proposed/joined | Create; view and revise own drafts or returned requests | Request changes to projects they own or proposed |
| Projects User | Compatibility alias for Project Proposer | Same as Project Proposer | Same as Project Proposer |
| Projects Manager | Every project, including recoverably removed projects | Every request and approval queue | Create requests; edit pending requests; approve, return, reject, or refresh stale requests |
| Project Viewer | Every approved project | None | Read-only |
| Project member — Basic | Projects where listed | None, unless another role grants it | Can work and claim; sees basic records and account labels only |
| Project member — Financial | Projects where listed | None, unless another role grants it | Can work and claim; also sees project budgets, allocations, revisions and Financial documents |

Accounts, audit, receipt-review, HR and expense-approval roles retain the
company-wide project visibility needed for their existing duties. That does not
make them Projects Managers or let them decide project proposals. Project roles
do not grant Account, payment, receipt-review or expense-approval authority.

## Approval lifecycle

New projects and every later configuration change use immutable requests:

1. The proposer saves a **Draft** and attaches supporting records.
2. Submission changes it to **Pending Approval**. No effective Project exists
   yet for a new request; a change request leaves the approved Project untouched.
3. Any one Projects Manager may:
   - edit the requested details and approve;
   - approve unchanged;
   - return it with comments as **Correction Required**;
   - reject it with comments; or
   - explicitly refresh a stale approved-project baseline before deciding.
4. Approval atomically creates or updates the effective Project and preserves
   actor, time, comments and before/after data in the request history.

Only one Projects Manager decision is required. Optimistic locking prevents a
manager from approving a request based on an older Project version, and only one
pending change request may exist per Project. Submitted requests cannot be
silently edited by their proposer. Rejected, withdrawn and approved requests are
retained.

Unused Projects may be recoverably removed by a Projects Manager. Projects with
financial records are never deleted; use completion or cancellation instead.

## Project structure

- **Identity:** name, purpose/scope, optional dates, outcomes, optional type and
  priority. Company is always Sevamrita Foundation and is not exposed as a form
  choice.
- **Lifecycle:** Planned, Active, On Hold, Completed, Cancelled. Only Active,
  financially open projects accept new or resubmitted spending.
- **People:** one enabled System User owner plus explicit members. Each member is
  Basic or Financial. Both levels can submit bills; the level controls visibility,
  not claim eligibility.
- **Cost centre:** one Sevamrita leaf Cost Centre. Departmental budgets are not
  shown in this Home workflow.
- **Project budget:** No Control, Warn Only or Strict and an overall approved
  amount.
- **Expense-account budgets:** independently No Control, Warn Only or Strict.
  Permitted accounts use a typing/search selector over existing Sevamrita leaf
  Expense accounts. Employee-facing labels are shown to claimants; ledger
  balances and the full Chart of Accounts are not exposed.
- **Supporting records:** private Basic or Financial documents attached to the
  request. On approval, scoped private File records are published to the Project;
  originals remain on the immutable request.

A Project may intentionally have no active permitted account while account
control is No Control. It then offers no account choice and cannot accept an
employee claim until an approved change activates one. Warn Only and Strict
account controls continue to require meaningful account allocations.

## Expense and accounting behaviour

Every explicitly listed Basic or Financial member may submit an Expense Claim
or Purchase Order against an Active project. Nonmembers are rejected. The
employee sees only the active account labels permitted by that Project. Server
validation resolves and checks the underlying ledger account, so hidden account
fields cannot be forged.

Budget modes remain independent at total-project and expense-account level:

- **No Control:** track commitments without an amount ceiling.
- **Warn Only:** show the overrun but allow the existing approval workflow.
- **Strict:** block approval unless the budget is revised or an existing
  authorised financial override applies.

Committed spending is Expense Claims plus Purchase Orders, not advances.
Receipt review, manager/grade expense approval and Accounts settlement remain
company-wide responsibilities and are not replaced by project membership.

## Privacy and security

- Basic members and Project Viewers do not receive project totals, account
  allocations, revision values, committed amounts or Financial attachments.
- Financial members and existing authorised finance/audit roles receive the
  financial Project permission level dynamically.
- Supporting files are private; File list queries and download checks enforce
  Project or Proposal scope and Basic/Financial visibility.
- Frappe DocShare cannot expand project membership, financial visibility or
  proposal access.
- Direct structured-Project saves and deletes are blocked even when a generic
  Desk permission or `ignore_permissions` path is attempted.
- Project proposals and generated budget revisions cannot be edited or deleted
  directly.

## Existing database compatibility

Migration is additive. Existing version-0 Projects are left untouched: it does
not guess owners or members, rewrite historical transactions, delete shares, or
assign roles. A legacy Project adopts the structured workflow only through an
approved request containing its real scope, owner, members and financial setup.
Historical accounting documents continue to settle after later lifecycle or
membership changes; the restrictions apply when new/draft spending is raised or
resubmitted.

## Local verification

Backend:

```sh
bench --site sevamrita.local run-tests --app volunteering \
  --module volunteering.volunteering.test_project_workspace
bench --site sevamrita.local run-tests --app volunteering \
  --module volunteering.volunteering.test_project_expense_accounts
```

Opt-in governed browser journey (localhost only):

```sh
BASE_URL=http://127.0.0.1:8001 npx playwright test \
  --config playwright.projects.config.ts
```

The browser journey uses local demo users and creates only `_Demo governed
project …` records and private text evidence; it never creates a real payment.
Do not run database-writing backend tests concurrently with it.

For staging, take a backup, deploy the feature branch, migrate the site, build
the SPA, assign real roles deliberately, and test with staging data before any
production merge. Migration never seeds demo users.
