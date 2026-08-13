# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""In-app Wiki content for HR (work log, attendance, leave, WFH, config).

Written in simple English so it is easy to read for everyone.
"""

HR_HOME = """# HR & attendance

Guides for daily work, attendance, leave, and work from home.

## For every employee

1. [Daily Work Log](/help/hr/daily-work-log) — write down your work each day
2. [Work From Home](/help/hr/work-from-home) — get approval before you work from home
3. [Leave](/help/hr/leave) — normal leave and emergency leave
4. [Attendance](/help/hr/attendance) — how Present, Absent, and Half Day are decided

## For managers

- [Manager guide](/help/hr/manager-guide) — approve requests, write manager notes, use dashboards

## For HR and admins

- [HR Configuration](/help/hr/configuration) — assign managers, grades, and set up policies
- [HR Settings & Ops](/help/hr/settings) — day-to-day HR tasks and policy details

## Quick links

| Task | Open |
|------|------|
| New work log | [Daily Work Log](/app/daily-work-log/new) |
| My work logs | [Daily Work Log list](/app/daily-work-log) |
| Request work from home | [Attendance Request](/app/attendance-request/new) |
| Apply for leave | [Leave Application](/app/leave-application/new) |
| Fix a wrong attendance day | [Attendance Regularization](/app/attendance-regularization-request/new) |
| My work hub | [My Work](/app/my-work) |
| My expenses hub | [My Expenses](/app/my-expenses) |

Related: [How to spend](/help/accounts/how-to-spend) · [Accounts: Tally → ERPNext](/help/accounts/tally-to-erpnext)
"""

HR_DAILY_WORK_LOG = """# Daily Work Log

Write down what you did each day. Your attendance is mostly decided from these hours, so please fill it in every working day.

## Who does what

- **Employee** — create and submit your own log
- **Manager** — see your team's logs and mark them **Reviewed**
- **HR / System Manager** — full access

## How to fill it in

1. Open [New Daily Work Log](/app/daily-work-log/new) (or use the button on your [Employee](/app/employee) page).
2. Choose the **Date**. You can only go back a few days (default is 2 days).
3. Add **items**. For each item, write the task, choose the **Project** (needed), write a short description, and enter the hours.
4. Only tick **Work From Home** if your work-from-home request for that date is already approved.
5. Click **Save**, then **Submit**.

After you submit, the status becomes **Submitted**, and your attendance for that day is updated.

## Hours guide

| Setting (default) | What it means |
|-------------------|---------------|
| Minimum hours warning (6) | You get a soft warning if your total hours are below this. |
| Present hours (6) | If you log this many hours or more, you are marked Present. |

## The stages of a log

Draft → **Submitted** → (manager may mark) **Reviewed** → or **Cancelled**

- After a log is **Reviewed**, you cannot change it.
- If a log is cancelled, your attendance is worked out again without those hours.

## Tips

- One log per person per day.
- Choose the correct project so the work is counted in the right place.
- To find days you missed: [Missing Daily Logs Report](/app/query-report/Missing%20Daily%20Logs%20Report)

Settings: [Daily Work Log Settings](/app/daily-work-log-settings/Daily%20Work%20Log%20Settings)

Back to [HR Home](/help/hr/home)
"""

HR_ATTENDANCE = """# Attendance

Attendance is mostly **automatic**. You do not need to mark yourself Present every day.

## How your status is decided

The system checks these in order (top one wins):

1. An **approved attendance fix** for that day — this locks the status.
2. **Approved leave** → On Leave
3. **Holiday** or weekly off → Holiday
4. **Approved work from home** with logged hours → Work From Home
5. Logged hours are **6 or more** → Present
6. Logged hours are more than 0 but less than 6 → Half Day
7. Nothing logged in time → Absent

## The grace time

The system finishes **yesterday's** attendance at **12:00 noon the next day**.

Example: Monday's attendance is finished on Tuesday at noon. If you submit a late work log before that time (and within the backdate limit), the day can still be corrected.

## Where to look

Open [Attendance](/app/attendance) to see your days. **Regularized** means a manager or HR approved a fix for that day.

## How to fix a wrong day

1. Best way: submit or correct your [Daily Work Log](/help/hr/daily-work-log) within the allowed days.
2. Or raise an [Attendance Fix Request](/app/attendance-regularization-request/new). Write the reason and the status you want (Present, Half Day, Work From Home, and so on).
3. Your **manager** or HR will approve or reject it. Only one open request per person per day.

## Unpaid staff

People with employment type **Unpaid** are not included in automatic attendance or in the summary emails. See [HR Configuration](/help/hr/configuration).

## Automatic job

Every day at **12:00 noon**: the system finishes yesterday's attendance and can send a summary email.

Back to [HR Home](/help/hr/home)
"""

HR_WFH = """# Work From Home

To work from home, you first ask for approval, and then you log your hours as usual.

## Steps

1. Create an [Attendance Request](/app/attendance-request/new). Set the reason to **Work From Home** and choose the date or dates.
2. Your **manager approves it** by submitting the request. You cannot approve your own request.
3. On the day you work from home, submit a [Daily Work Log](/app/daily-work-log/new) and tick **Work From Home**.
4. With approval and logged hours, your attendance for that day becomes **Work From Home**.

## Important rules

| Your situation | Result |
|----------------|--------|
| Approved + hours logged | Work From Home |
| Approved + **no** hours in time | Absent |
| Work log ticked as home **without** approval | Not allowed |

Managers can cancel or change a request if needed.

## Related

- [Daily Work Log](/help/hr/daily-work-log)
- [Attendance](/help/hr/attendance)

Back to [HR Home](/help/hr/home)
"""

HR_LEAVE = """# Leave Application

To apply for leave, open a [Leave Application](/app/leave-application/new). Choose the **type**: Normal or Emergency.

## Leave types

| Type | Use it for |
|------|-----------|
| **Privilege Leave** | Normal paid leave. You earn it every month (up to about 30 days a year). |
| **Leave Without Pay** | Time off with no pay. |

Every application needs a **Leave Approver**. This is usually your manager, and it is set for you automatically.

## Normal leave

- **No past dates** — the start date must be today or later.
- You must give notice. For an N-day leave, give at least **N days** notice.
  Example: a 3-day leave needs at least 3 days between today and the start date.
- If you need leave at short notice, use **Emergency** leave instead.

## Emergency leave

- Up to **3 days in a row**.
- You can apply after the fact, but you must do it within **48 hours** of coming back. HR can add it later if needed.
- For longer time off, use Normal leave with notice.

## Long leave (more than 7 days)

For leave longer than 7 days, the approver must be an employee on the **Board of Directors** grade.

## After approval

Approved leave sets your attendance to **On Leave** for those days.

## Leave balance looks wrong?

If your Privilege Leave balance looks too high, ask HR to check your leave records.

Settings: [Leave Policy Settings](/app/leave-policy-settings/Leave%20Policy%20Settings)

Back to [HR Home](/help/hr/home)
"""

HR_MANAGER = """# Manager guide

You approve requests for the people who report to you. This follows the **Reports To** chain on the Employee page.

## What you approve

| Request | How you approve it |
|---------|--------------------|
| [Work From Home](/app/attendance-request) | Open the request → **Submit** |
| [Leave Application](/app/leave-application) | Use the Approve or Reject button (you must be the leave approver) |
| [Attendance Fix](/app/attendance-regularization-request) | Open it → Approve or Reject |
| [Daily Work Log](/app/daily-work-log) | Optional: **Mark as Reviewed** |

You cannot approve your own work-from-home or leave.

## Manager notes

You can write private notes about the people who report to you (at any level below you):

- Types: Appreciation, Coaching, or Warning.
- Notes are add-only. **Employees never see them.**
- You can link a note to a work log.

## Dashboards

| Page | Who | Open |
|------|-----|------|
| My Work | Employees | [My Work](/app/my-work) |
| My Expenses | Employees / Accounts | [My Expenses](/app/my-expenses) |
| HR Accountability | HR / System Manager | [HR Accountability](/app/hr-accountability) |
| Missing Daily Logs | Managers / HR | [Report](/app/query-report/Missing%20Daily%20Logs%20Report) |

## Keep the reporting chain correct

Make sure each person's **Reports To** is set correctly. If it is wrong, requests go to the wrong approver. See [HR Configuration](/help/hr/configuration).

Also see: [HR Settings](/help/hr/settings) · [HR Home](/help/hr/home)
"""

HR_CONFIG = """# HR Configuration

This page shows **where** to assign managers and other HR settings. It is for HR Managers and System Managers.

## 1. Give a person a manager (most important)

A person's manager is set with the **Reports To** field on their Employee page.

1. Open the person's [Employee](/app/employee) page.
2. In **Reports To**, choose their manager.
3. Save.

When you do this, the system automatically:

- Sets the manager as the person's **Leave Approver**.
- Gives the manager the ability to approve that person's leave, work-from-home, and attendance fixes.
- Sends spending approvals up this chain (see [Accounts Configuration](/help/accounts/configuration)).

> Keep Reports To correct for everyone. If it is wrong, requests go to the wrong person.

## 2. Check the leave approver

The **Leave Approver** field on the Employee page is filled in from Reports To automatically. You usually do not need to change it. Only change it by hand if someone needs a different approver.

## 3. Give a person a grade (approval band)

**Designation** is the job title. **Grade** decides how much a person can approve and how large an advance they can take.

1. Open the person's [Employee](/app/employee) page.
2. Set the **Designation** (job title, for example Programme Officer).
3. Choose the **Grade** (for example, Manager, Director, Board of Directors).
4. Save.

The amounts for each grade are set by Accounts. See [Accounts Configuration](/help/accounts/configuration).

## 4. Set the department and department head

1. Open a [Department](/app/department).
2. Set the **Department Head**.
3. On each Employee page, set their **Department**.

This helps route some approvals and reports correctly.

## 5. Mark unpaid staff

For volunteers or unpaid staff, set **Employment Type = Unpaid** on their Employee page. Then they are:

- Left out of automatic attendance,
- Left out of the default leave policy,
- Left out of the summary emails.

## 6. Policy settings

| Setting | Where | What you set |
|---------|-------|--------------|
| Daily Work Log Settings | [Open](/app/daily-work-log-settings/Daily%20Work%20Log%20Settings) | Backdate limit, minimum hours, present hours, summary email |
| Leave Policy Settings | [Open](/app/leave-policy-settings/Leave%20Policy%20Settings) | Default leave type, emergency days, long-leave rules |

## 7. Work log summary email

On [Daily Work Log Settings](/app/daily-work-log-settings/Daily%20Work%20Log%20Settings) you can turn on an email that summarises everyone's work logs.

You can choose:

- **Who** gets it — by role, plus any extra email addresses.
- **From** which email address it is sent.
- **How often** — daily, weekly, or monthly.

Use **Preview Summary** to see how it looks, and **Send Summary Now** to send it at once.

## New employees

When you add a new employee, the standard leave policy is given to them automatically (unless they are Unpaid). Remember to set their **Reports To**, **Designation** (job title) and **Grade** (approval band).

## Related

- [Manager guide](/help/hr/manager-guide)
- [HR Settings & Ops](/help/hr/settings)
- [Accounts Configuration](/help/accounts/configuration)
"""

HR_SETTINGS = """# HR settings & ops

For HR Managers and System Managers. For how to assign managers and grades, see [HR Configuration](/help/hr/configuration).

## Settings pages

| Page | Open | Main fields |
|------|------|-------------|
| Daily Work Log Settings | [Open](/app/daily-work-log-settings/Daily%20Work%20Log%20Settings) | Backdate limit, minimum hours, present hours, attendance job, summary email |
| Leave Policy Settings | [Open](/app/leave-policy-settings/Leave%20Policy%20Settings) | Default leave type, unpaid leave type, emergency days, long-leave rules |

## Standard data (added on setup)

- Leave types: Privilege Leave, Leave Without Pay
- Leave policy: the standard policy (earned every month)
- Leave period: usually April to March
- Employment type: **Unpaid**
- Holiday lists

New employees get the standard leave policy automatically (except Unpaid staff).

## Unpaid staff

Set **Employment Type = Unpaid** on the Employee page. Effects:

- No automatic attendance
- No default leave policy
- Not included in the summary email

They can still use the system if their roles allow it.

## Who can do what

| Task | Employee | Manager | HR |
|------|----------|---------|-----|
| Daily Work Log | Own | See team; Review | Full |
| Work From Home | Own | Approve for team | Full |
| Leave Application | Own | Approve (if approver) | Full |
| Attendance Fix | Own | Approve or Reject | Full |
| Manager Notes | No access | For team | Full |

## Automatic job

Every day at **12:00 noon**: the system finishes yesterday's attendance and sends the summary email if it is turned on.

## Related guides

- [HR Configuration](/help/hr/configuration)
- [HR Home](/help/hr/home)
- [Attendance](/help/hr/attendance)
- [Leave](/help/hr/leave)
- [How to spend](/help/accounts/how-to-spend)
"""
