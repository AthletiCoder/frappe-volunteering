# HR & attendance wiki

## If pages 404

Wiki v3 treats an empty role table as **logged-in only**. Guests see “Page not found”.
After migrate, Sevamrita Wiki space gets **Guest / Employee Read** so `/help/...` links work.

Also **restart `bench start`** after installing wiki so web workers load the app.

## View (website)

| Topic | URL |
|-------|-----|
| HR home | `/help/hr/home` |
| Daily Work Log | `/help/hr/daily-work-log` |
| Attendance | `/help/hr/attendance` |
| Work From Home | `/help/hr/work-from-home` |
| Leave | `/help/hr/leave` |
| Manager guide | `/help/hr/manager-guide` |
| HR settings | `/help/hr/settings` |
| How to spend | `/help/accounts/how-to-spend` |
| Tally → ERPNext | `/help/accounts/tally-to-erpnext` |

Space hub: `/help` (redirects to first page).

## Edit (Desk)

Use **Wiki Document** (not the deprecated Wiki Page).

Or open the Wiki app UI: `/wiki` → space **Sevamrita Wiki**.

## Seed

`volunteering.volunteering.wiki_setup.ensure_help_wikis` runs on migrate.

## Team charter effective 1 December 2026

The Home website at `/volunteering/time-leave` and the native SF Tasks
**Time and leave** screen share the same request, review and People centre APIs.
Employees see their own requests and payslips. Direct managers see their team's
requests. HR Managers and System Managers can publish dated policy revisions,
adjust balances and record reasoned exceptions; they cannot approve their own
leave. Accounts Managers can also maintain payroll profiles and ledger mappings.

The migration seeds the December revision once. Earlier policy snapshots and
attendance are retained. The revised rules allow four days for work logging,
count 3 to under 6 logged hours as half a day, require 6 hours for a full day,
and extend compensatory credit to two months. Under three hours is unpaid
unless approved leave or a documented HR correction covers the absence.
Automatic attendance and leave rules apply to salaried staff; work logging
remains available to volunteers. Annual leave uses January–December, accrues
2.5 days per month and allows up to 15 carried-forward days.

All revised leave and weekly-off swaps route to the direct reporting manager.
Medical requests waive advance notice and record when the manager was informed.
A private medical certificate is required before approving an absence exceeding
two consecutive calendar days, unless HR records an exception. Certificates can
be uploaded with the request or added to an open request later (PDF, PNG or JPEG,
up to 5 MB).

Maternity, paternity and optional holidays have separate allocations. Parental
requests record the expected/actual childbirth date; HR must verify eligibility
before the manager approves. Maternity defaults to 26 calendar weeks for the
standard eligible case, with the shorter applicable cases available separately.
Paternity is five working days within three months of childbirth. The HR
verification action records the reviewer and explanation; it does not infer
statutory eligibility from an employee name or designation.

### HR setup in People centre

1. **Holidays:** publish the twelve fixed holidays and designated optional dates
   for each calendar year. Employees can reserve at most two optional days,
   including requests awaiting approval. The supplied deck does not contain its
   referenced 2027 date appendix, so festival dates are intentionally unseeded.
   Existing leave and submitted payroll protect affected dates against edits.
   From the charter effective date, these published fixed dates replace inherited
   non-weekly holidays; they are not added on top of an older holiday list. Weekly
   offs continue to apply while the confirmed festival calendar is being filled.
2. **Edit guide:** maintain the organisation guide, contacts and working-day
   expectations. The employee reporting form updates actual Employee records,
   checks reporting cycles and requires an audit reason. Editing a name in the
   published guide does not silently change an Employee record.
3. **HR policy & balances:** publish effective-dated numeric rules and make
   reasoned balance/attendance exceptions. Existing April–March leave allocations
   require explicit HR adoption into the calendar-year policy; the portal does
   not silently replace their balances.
4. **Payroll:** explicitly enrol each employee for PF and/or Professional Tax,
   choose the Basic salary component, enter effective monthly values and record
   exemptions. Configure PF and PT liability ledgers before submitting salaries.
   Profile revisions and submitted salaries protect historical payroll.

The preview uses the configured monthly values; actual Salary Slips continue to
use the employee's Salary Structure/Assignment. Calendar-day payroll divides by
the actual 28/29/30/31 days in the month. Employee PF and Maharashtra PT are
deductions; employer PF is shown separately as an employer contribution and is
excluded from take-home deductions. Employer contribution accounting/remittance
continues through the organisation's payroll accounting process; merely viewing
the preview does not post a journal or remit PF/PT.

The deck's ₹25,000 PF ceiling is a configurable **company policy**. It is not the
general EPFO statutory ₹15,000 wage ceiling; higher-wage contribution arrangements
must be verified before enrolment. Maharashtra PT slabs, February amounts and
employee exemptions are configurable rather than inferred for every employee.
Reference sources: [EPFO contribution rates](https://www.epfindia.nic.in/site_docs/PDFs/MiscPDFs/ContributionRate.pdf),
[Maharashtra PT schedule](https://cdnbbsr.s3waas.gov.in/s36a4cbdaedcbda0fa8ddc7ea32073c475/uploads/2026/02/202602161497231504.pdf),
[Maternity Benefit amendment clarifications](https://labour.gov.in/sites/default/files/the_maternity_benefit_amendment_act2017_-clarifications.pdf).

### Regression coverage

`test_team_charter`, `test_time_leave_portal`, `test_leave_policy`,
`test_attendance_service`, `test_work_log_portal`, `test_home_service`,
`test_attendance_digest` and `test_people_management` cover the backend rules and
access controls. `team-charter.spec.ts` and `time-leave.spec.ts` exercise the Home
forms at desktop and phone widths. They require explicit isolated local HR
fixtures (`E2E_HR_FIXTURES`), with a generated blank PDF supplied through
`E2E_MEDICAL_PDF` for certificate upload tests. They must not target production.
Android debug/release unit tests and APK compilation validate the shared native
implementation. On 25 November 2026, the employee → HR eligibility verification →
reporting-manager approval flow was also exercised on a physical Android phone.
This uncovered and fixed inherited medical/half-day form fields, misleading
optional wording for the required childbirth date, and HR validation failures
caused by the automatic own-Employee restriction. HR validation scopes that
restriction only in the request-local cache; it does not change saved User
Permissions or the acting user. Time and leave now offers account switching,
and an HR action denial no longer clears its navigation permissions.
