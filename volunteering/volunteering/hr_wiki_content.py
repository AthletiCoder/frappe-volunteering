# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""In-app Wiki content for HRMS (work log, attendance, leave, WFH)."""

HR_HOME = """# HR & attendance

Guides for daily work, attendance, leave, and work from home.

## For every employee

1. [Daily Work Log](/help/hr/daily-work-log) — log work each day
2. [Work From Home](/help/hr/work-from-home) — request WFH before logging WFH hours
3. [Leave](/help/hr/leave) — Normal vs Emergency leave
4. [Attendance](/help/hr/attendance) — how Present / Absent / Half Day is decided

## For managers

- [Manager guide](/help/hr/manager-guide) — approve WFH, leave, regularization; Manager Notes; dashboards

## For HR

- [HR settings](/help/hr/settings) — policies, thresholds, unpaid staff, digests

## Quick links

| Task | Open |
|------|------|
| New work log | [Daily Work Log](/app/daily-work-log/new) |
| My work logs | [Daily Work Log list](/app/daily-work-log) |
| Request WFH | [Attendance Request](/app/attendance-request/new) |
| Apply leave | [Leave Application](/app/leave-application/new) |
| Fix attendance | [Attendance Regularization](/app/attendance-regularization-request/new) |
| Self-service hub | [My Work](/app/my-work) |
| Expenses hub | [My Expenses](/app/my-expenses) |

Related: [How to spend](/help/accounts/how-to-spend) (expenses) · [Accounts: Tally → ERPNext](/help/accounts/tally-to-erpnext)
"""

HR_DAILY_WORK_LOG = """# Daily Work Log

Record what you worked on each day. Attendance is computed largely from these hours.

## Who

- **Employee** — create and submit your own log
- **Reporting manager** — view reportees’ logs; mark **Reviewed**
- **HR / System Manager** — full access

## How to submit

1. Open [New Daily Work Log](/app/daily-work-log/new) (or use the button on your [Employee](/app/employee) form).
2. Set **Date** (backdating is limited — default **2 days**; see Daily Work Log Settings).
3. Add **items**: task title, **Project** (required), description (min length enforced), hours, optional output link.
4. Optional: tick **Work From Home** only if you already have an **approved** Attendance Request for that date.
5. **Save**, then **Submit**.

After submit, status becomes **Submitted** and attendance for that date is refreshed.

## Hours guidance

| Setting (defaults) | Meaning |
|--------------------|---------|
| Min hours warning (6) | Soft warning if total hours are below this |
| Present hours threshold (6) | Used by attendance: ≥ threshold → Present (see [Attendance](/help/hr/attendance)) |

## Status lifecycle

Draft → **Submitted** → optionally **Reviewed** (manager) → or **Cancelled**

- Once **Reviewed**, you cannot edit the log.
- Cancelling a log recomputes attendance without those hours.

## Tips

- One log per employee per date (naming: `{employee}-{date}`).
- Use real projects so work rolls up correctly.
- Missing logs: [Missing Daily Logs Report](/app/query-report/Missing%20Daily%20Logs%20Report)

Settings: [Daily Work Log Settings](/app/daily-work-log-settings/Daily%20Work%20Log%20Settings)

Back to [HR Home](/help/hr/home)
"""

HR_ATTENDANCE = """# Attendance

Attendance is mostly **automatic**. You do not mark Present every day by hand.

## How status is decided

Priority (highest first):

1. **Approved Attendance Regularization** for that date (locks the status)
2. **Approved Leave** → On Leave
3. **Holiday** / weekly off → Holiday (hours may still exist if you logged work)
4. **Approved WFH** + submitted work hours → Work From Home
5. Submitted hours ≥ **Present threshold** (default 6h) → Present
6. Submitted hours above 0 but below threshold → Half Day
7. Otherwise after grace → Absent

## Grace period

The noon job finalizes the **previous** calendar day. Grace runs until **next day 12:00**.  
Example: Monday’s attendance is finalized at Tuesday noon. Submitting a late work log within grace (and backdate limit) can still correct the day.

## What you see

Open [Attendance](/app/attendance) for your records. The field **Regularized** means a manager/HR approved an [Attendance Regularization Request](/app/attendance-regularization-request).

## Fixing a wrong day

1. Prefer: submit/correct [Daily Work Log](/help/hr/daily-work-log) within backdate + grace rules.
2. Or raise [Attendance Regularization](/app/attendance-regularization-request/new) with reason and requested status (Present / Half Day / WFH / Absent / On Leave / Holiday).
3. Your **reporting manager** or HR Approves or Rejects. One open/approved request per employee+date.

## Unpaid staff

Employees with Employment Type **Unpaid** are excluded from automatic attendance and board digests. See [HR Settings](/help/hr/settings).

## Scheduled jobs

Daily at **12:00**: process yesterday’s attendance + optional Executive Board digest email.

Back to [HR Home](/help/hr/home)
"""

HR_WFH = """# Work From Home (WFH)

WFH uses HRMS **Attendance Request** with reason **Work From Home**.

## Steps

1. Employee creates [Attendance Request](/app/attendance-request/new) — set reason to **Work From Home**, choose date(s).
2. **Reporting manager submits** the request (that is the approval). You cannot approve your own request.
3. On the WFH day, submit a [Daily Work Log](/app/daily-work-log/new) and tick **Work From Home** (or the system detects the approved request).
4. With approved WFH + submitted hours → Attendance status **Work From Home**.

## Important rules

| Situation | Result |
|-----------|--------|
| WFH approved + hours logged | Work From Home |
| WFH approved + **no** hours after grace | Absent |
| Work log marked WFH **without** approved request | Blocked |

Managers can cancel/amend Attendance Requests per HRMS rules.

## Related

- [Daily Work Log](/help/hr/daily-work-log)
- [Attendance](/help/hr/attendance)

Back to [HR Home](/help/hr/home)
"""

HR_LEAVE = """# Leave Application

Use [Leave Application](/app/leave-application/new). Choose **Leave Category**: Normal or Emergency.

## Leave types

| Type | Use |
|------|-----|
| **Privilege Leave** | Standard paid leave (earned monthly under Sevamrita Standard Leave Policy; max ~30/year) |
| **Leave Without Pay** | Unpaid absence |

A **Leave Approver** is mandatory (set on Employee / application).

## Normal leave

- **No backdating** — from-date must be today or later
- Advance notice: for an N-day leave you need at least **N days** notice before from-date  
  Example: 3-day Normal leave needs ≥ 3 days between today and start date
- For short-notice absence, use **Emergency** instead

## Emergency leave

- Max **3 consecutive days** (configurable in Leave Policy Settings)
- Retroactive: must regularize within **48 hours** of return (to-date). HR/System Manager can backfill beyond that window
- Longer absences: use Normal leave with notice, or escalate to leadership

## Long leave (more than 7 days)

Leave Approver must have the **Executive Board Chairperson** role.

## After approval

Approved leave drives Attendance **On Leave** for those dates.

## Balance issues (around 60 days)

Duplicate old allocations can inflate Privilege Leave. Ask HR to check Leave Allocations / Leave Policy Assignment, or see the ops note `docs/unpaid_and_leave_ops.md` in the volunteering app.

Settings: [Leave Policy Settings](/app/leave-policy-settings/Leave%20Policy%20Settings)

Back to [HR Home](/help/hr/home)
"""

HR_MANAGER = """# Manager guide (HRMS)

You approve and coach via the **Reports To** hierarchy on Employee.

## What you approve

| Request | How you approve |
|---------|-----------------|
| [Attendance Request](/app/attendance-request) (WFH) | Open the draft → **Submit** |
| [Leave Application](/app/leave-application) | HRMS leave approver actions (you must be the Leave Approver) |
| [Attendance Regularization](/app/attendance-regularization-request) | Actions → Approve or Reject |
| [Daily Work Log](/app/daily-work-log) | Optional: **Mark as Reviewed** (does not change attendance alone) |

You cannot approve your own WFH or leave.

## Manager Notes

Create [Manager Notes](/app/manager-note/new) for reportees (any depth in the tree):

- Types: Appreciation / Coaching / Warning
- Append-only; **employees never see** these notes
- Optional link to a Daily Work Log
- May appear in the Executive Board attendance digest when configured

## Dashboards

| Workspace | Who | Route |
|-----------|-----|-------|
| My Work | Employees | [/app/my-work](/app/my-work) |
| My Expenses | Employees / Accounts | [/app/my-expenses](/app/my-expenses) |
| HR Accountability | HR Manager / System Manager | [/app/hr-accountability](/app/hr-accountability) |
| Missing Daily Logs | Managers / HR | [Report](/app/query-report/Missing%20Daily%20Logs%20Report) |

## Reporting chain

Keep **Employee → Reports To** and **Leave Approver** up to date. Wrong hierarchy = wrong approver.

Also see: [HR Settings](/help/hr/settings) · [HR Home](/help/hr/home)
"""

HR_SETTINGS = """# HR settings & ops

For HR Managers and System Managers.

## Singles to configure

| Setting | Path | Key fields |
|---------|------|------------|
| Daily Work Log Settings | [/app/daily-work-log-settings](/app/daily-work-log-settings/Daily%20Work%20Log%20Settings) | Backdate limit days, min hours warning, present hours threshold, enable attendance job, board digest |
| Leave Policy Settings | [/app/leave-policy-settings](/app/leave-policy-settings/Leave%20Policy%20Settings) | Default leave type, LWP type, emergency max days, director approval days, default policy/period |

## Masters (seeded on migrate)

- Leave Type: Privilege Leave, Leave Without Pay
- Leave Policy: Sevamrita Standard Leave Policy (earned monthly)
- Leave Period: typically Apr–Mar FY
- Employment Type: **Unpaid**
- Holiday lists: Wednesday weekly off (org-specific)

New Employees get the default leave policy assigned automatically (except Unpaid).

## Unpaid employment type

On the Employee record set **Employment Type = Unpaid**. Effects:

- Excluded from auto attendance
- Excluded from default Privilege Leave policy assignment
- Excluded from Executive Board attendance digest  
They can still use Desk manually if roles allow.

Ops detail: `docs/unpaid_and_leave_ops.md` in the volunteering app.

## Permissions snapshot

| DocType | Employee | Manager | HR |
|---------|----------|---------|-----|
| Daily Work Log | Own create/submit | View reportees; Review | Full |
| Attendance Request | Own create | Submit (approve) reportees | Full |
| Leave Application | Own apply | Leave Approver | Full |
| Attendance Regularization | Own create | Approve/Reject | Full |
| Manager Note | No access | Create for reportees | Full |

## Digests & cron

- **12:00 daily**: finalize previous day’s attendance; send board digest if enabled  
- Configure extra digest recipients on Daily Work Log Settings

## Related guides

- [HR Home](/help/hr/home)
- [Attendance](/help/hr/attendance)
- [Leave](/help/hr/leave)
- Expense/spend: [How to Spend](/help/accounts/how-to-spend)
"""
