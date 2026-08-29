# E2E coverage matrix

Source: `sevamrit-erp-testing.xlsx` (108 spreadsheet cases). All 108 IDs are automated in Playwright specs under `e2e/tests/`.

**Last verified:** Aug 2026 — suite converted to **browser UI** (`@ui`); API helpers limited to setup/assert.

**Execution:** All 108 spreadsheet IDs use **UI** for create/submit/approve. **API-setup** is used only for cleanup, fixtures, `trigger_attendance_job`, `set_advance_settlement`, and post-action `get_doc_field` / `get_attendance_status` assertions. Supplementary **VO-001…006** gap tests in `e2e/tests/volunteering/gap.spec.ts`.

**Level rules:** Cases in `*/smoke.spec.ts` without `@regression`/`@critical` tags are **smoke**. Others use **critical** when the spec line has `@critical`, else **regression**.

**Convention:** `test()` titles start with the spreadsheet ID (e.g. `HR-DWL-001`, `AC-ADV-001`, `XM-001`).

## HR (59)

| ID | Title (short) | Level | Spec file | Status |
|----|---------------|-------|-----------|--------|
| HR-ATT-001 | No log after grace marks Absent | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-002 | Late work log corrects Absent to Present | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-003 | Holiday takes priority over logged hours | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-004 | Approved leave takes priority over work log | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-005 | Regularization locks status to Present | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-006 | Only one open regularization per day | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-007 | Manager rejects regularization | regression | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-008 | Unpaid employee excluded from attendance job | critical | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-009 | Regularization beats approved leave | regression | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-ATT-010 | View own attendance list | regression | `e2e/tests/hr/attendance.spec.ts` | automated |
| HR-CFG-001 | Setting Reports To syncs Leave Approver | critical | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-002 | Wrong Reports To routes approvals incorrectly | critical | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-003 | Designation set on Employee | regression | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-004 | Department Head and Employee Department | regression | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-005 | Unpaid employment type exclusions | critical | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-006 | Paid employee gets standard leave policy | critical | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-007 | Change Present hours setting affects attendance | regression | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-008 | Change backdate limit setting | regression | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-009 | Work log summary email preview | regression | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-010 | Leave Policy Settings page loads | regression | `e2e/tests/hr/config.spec.ts` | automated |
| HR-CFG-011 | Noon job finalizes yesterday attendance | critical | `e2e/tests/hr/config.spec.ts` | automated |
| HR-DWL-001 | Create and submit daily work log (happy path) | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-002 | Project is required on work log item | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-003 | One work log per employee per day | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-004 | Backdate within allowed limit | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-005 | Backdate beyond allowed limit blocked | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-006 | Soft warning when hours below minimum | regression | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-007 | Hours >= Present hours yields Present | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-008 | Hours between 0 and Present yields Half Day | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-009 | Manager review locks employee edits | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-010 | Cancel submitted log recalculates attendance | critical | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-011 | Employee can only create own work log | regression | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-012 | Missing Daily Logs Report lists missing days | regression | `e2e/tests/hr/daily-work-log.spec.ts` | automated |
| HR-DWL-013 | Home loads for employee | smoke | `e2e/tests/hr/smoke.spec.ts` | automated |
| HR-LV-001 | Normal Privilege Leave with sufficient notice | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-002 | Normal leave with past start date blocked | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-003 | Normal leave insufficient notice blocked | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-004 | Leave Without Pay application | regression | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-005 | Emergency leave within 3 consecutive days | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-006 | Emergency leave more than 3 consecutive days blocked | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-007 | Emergency leave within 48 hours after return | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-008 | Emergency leave after 48 hours without HR blocked | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-009 | HR can add late emergency leave | regression | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-010 | Long leave requires Board Chairperson approver | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-011 | Long leave approved by Board Chairperson | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-012 | Employee cannot approve own leave | critical | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-013 | Leave Approver auto-filled from Reports To | regression | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-LV-014 | Reject leave does not mark On Leave | regression | `e2e/tests/hr/leave.spec.ts` | automated |
| HR-MGR-001 | Manager creates Appreciation note for report | regression | `e2e/tests/hr/manager-notes.spec.ts` | automated |
| HR-MGR-002 | Employee cannot see manager notes | critical | `e2e/tests/hr/manager-notes.spec.ts` | automated |
| HR-MGR-003 | Manager note types Coaching and Warning | regression | `e2e/tests/hr/manager-notes.spec.ts` | automated |
| HR-MGR-004 | HR Accountability page loads for HR | regression | `e2e/tests/hr/manager-notes.spec.ts` | automated |
| HR-MGR-005 | Manager sees team work logs and marks reviewed | regression | `e2e/tests/hr/manager-notes.spec.ts` | automated |
| HR-WFH-001 | Request WFH and manager approves | critical | `e2e/tests/hr/wfh.spec.ts` | automated |
| HR-WFH-002 | Employee cannot approve own WFH | critical | `e2e/tests/hr/wfh.spec.ts` | automated |
| HR-WFH-003 | Approved WFH and hours logged yields Work From Home | critical | `e2e/tests/hr/wfh.spec.ts` | automated |
| HR-WFH-004 | Approved WFH without hours marks Absent after job | critical | `e2e/tests/hr/wfh.spec.ts` | automated |
| HR-WFH-005 | WFH tick without approval blocked | critical | `e2e/tests/hr/wfh.spec.ts` | automated |
| HR-WFH-006 | Manager cancel blocks WFH-ticked work log | regression | `e2e/tests/hr/wfh.spec.ts` | automated |

## Accounts (46)

| ID | Title (short) | Level | Spec file | Status |
|----|---------------|-------|-----------|--------|
| AC-ADV-001 | Self advance within Max Self Advance | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-002 | Self advance above Max Self Advance blocked | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-003 | Employee cannot create advance for another person | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-004 | Accounts can create advance for another | regression | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-005 | Large leftover blocks new advance | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-006 | Small leftover allows new advance | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-007 | Settle advance via Expense Claim link | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-008 | Get Advances hides unpaid advances | critical | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-009 | Advance Portal shows status | smoke | `e2e/tests/accounts/smoke.spec.ts` | automated |
| AC-ADV-010 | Employee Advances with Residual report | regression | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-ADV-011 | Manager self advance limit 5000 | regression | `e2e/tests/accounts/advance.spec.ts` | automated |
| AC-APR-001 | Approve when amount <= Max Approval Authority | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-002 | Cannot Approve when over authority; can Escalate | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-003 | Associate authority 0 cannot approve others | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-004 | Board-level can approve any amount | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-005 | Cannot approve own spending request | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-006 | Escalate follows Reports To chain | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-007 | Approval Authority toggle Off uses simple tiers | regression | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-APR-008 | Grade change updates effective limits | critical | `e2e/tests/accounts/approval.spec.ts` | automated |
| AC-BKS-001 | Cashfree clearing Journal Entry form reachable | regression | `e2e/tests/accounts/books.spec.ts` | automated |
| AC-BKS-002 | Cancel preserves history (submitted doc not deletable) | regression | `e2e/tests/accounts/books.spec.ts` | automated |
| AC-BKS-003 | Home loads for employee spend actions | smoke | `e2e/tests/accounts/smoke.spec.ts` | automated |
| AC-BKS-004 | General Ledger report runs | regression | `e2e/tests/accounts/books.spec.ts` | automated |
| AC-BKS-005 | Bank Reconciliation Tool opens | regression | `e2e/tests/accounts/books.spec.ts` | automated |
| AC-BUD-001 | Soft budget warning near budget | regression | `e2e/tests/accounts/budget.spec.ts` | automated |
| AC-BUD-002 | Hard block when overspend exceeds Budget Hard-Block % | critical | `e2e/tests/accounts/budget.spec.ts` | automated |
| AC-BUD-003 | Budget Override Role can exceed hard block | critical | `e2e/tests/accounts/budget.spec.ts` | automated |
| AC-BUD-004 | Budget Health page loads | smoke | `e2e/tests/accounts/smoke.spec.ts` | automated |
| AC-CLM-001 | Reimbursement happy path to Approved | critical | `e2e/tests/accounts/claim.spec.ts` | automated |
| AC-CLM-002 | Monthly Reimbursement Cap blocks excess | critical | `e2e/tests/accounts/claim.spec.ts` | automated |
| AC-CLM-003 | Monthly Reimbursement Cap 0 = unlimited | regression | `e2e/tests/accounts/claim.spec.ts` | automated |
| AC-CLM-004 | Reject expense claim | regression | `e2e/tests/accounts/claim.spec.ts` | automated |
| AC-CLM-005 | Claim requires receipts before submit | regression | `e2e/tests/accounts/claim.spec.ts` | automated |
| AC-MFL-001 | Out of Pocket firm reimbursement (not manager float) | critical | `e2e/tests/accounts/manager-float.spec.ts` | automated |
| AC-MFL-002 | Manager Advance approve settles from manager paid advance | critical | `e2e/tests/accounts/manager-float.spec.ts` | automated |
| AC-MFL-003 | Manager without float blocks Approve and allows Escalate | critical | `e2e/tests/accounts/manager-float.spec.ts` | automated |
| AC-MFL-004 | Advance Portal shows manager float panel | regression | `e2e/tests/accounts/manager-float.spec.ts` | automated |
| AC-MFL-005 | Advance Portal lists pending team manager-float request | regression | `e2e/tests/accounts/manager-float.spec.ts` | automated |
| AC-SET-001 | Accounts Manager edits Approval & Advance Limits | critical | `e2e/tests/accounts/settings.spec.ts` | automated |
| AC-SET-002 | HR Manager view-only on limits | critical | `e2e/tests/accounts/settings.spec.ts` | automated |
| AC-SET-003 | Edit Vendor Payment Threshold and Cash Payment Limit | regression | `e2e/tests/accounts/settings.spec.ts` | automated |
| AC-SET-004 | Cash payment within limit setting saved | regression | `e2e/tests/accounts/settings.spec.ts` | automated |
| AC-SET-005 | Advances are not tagged to a project | regression | `e2e/tests/accounts/settings.spec.ts` | automated |
| AC-VEN-001 | Happy path PO approve | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-002 | Purchase Invoice without approved PO blocked | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-003 | Staff cannot create Payment Entry | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-004 | Accounts can open Payment Entry form | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-005 | Pay vendor before bill (advance against PO) | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-006 | Mark Paid outside system creates Payment Entry | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-007 | Above vendor threshold without override blocked | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |
| AC-VEN-008 | Above threshold allowed with Vendor Payment Override Reason | critical | `e2e/tests/accounts/vendor.spec.ts` | automated |

## Cross-module (3)

| ID | Title (short) | Level | Spec file | Status |
|----|---------------|-------|-----------|--------|
| XM-001 | Reports To drives leave and spend approvals | critical | `e2e/tests/cross-module/shared-master.spec.ts` | automated |
| XM-002 | Grade change updates Accounts limits; HR still works | critical | `e2e/tests/cross-module/shared-master.spec.ts` | automated |
| XM-003 | Unpaid employee HR exclusions | regression | `e2e/tests/cross-module/shared-master.spec.ts` | automated |

## Ops / Volunteering smoke (supplementary)

Infrastructure and persona checks without spreadsheet IDs (not counted in the 108).

| ID | Title (short) | Level | Spec file | Status |
|----|---------------|-------|-----------|--------|
| — | Site ping responds | smoke | `e2e/tests/ops/smoke.spec.ts` | automated |
| — | Authenticated session is not Guest | smoke | `e2e/tests/ops/smoke.spec.ts` | automated |
| — | Email Queue readable via API | smoke | `e2e/tests/ops/smoke.spec.ts` | automated |
| — | Email Queue desk list opens | smoke | `e2e/tests/ops/smoke.spec.ts` | automated |
| — | E2E cast seeded (employee, coordinator, volunteer) | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | ensure_fixtures returns project and department | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | Event registration form reachable | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | Coordinator session is e2e.coordinator | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | Volunteer session is e2e.volunteer | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | get_home_payload API contract | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | get_budget_health API contract | smoke | `e2e/tests/volunteering/smoke.spec.ts` | automated |
| — | Employee / manager / chair persona sessions | smoke | `e2e/tests/shared/persona-smoke.spec.ts` | automated |
| — | Employee can open Advance Portal | smoke | `e2e/tests/shared/persona-smoke.spec.ts` | automated |
| — | Digest preview API (ops path) | regression | `e2e/tests/ops/config.spec.ts` | automated |
| — | Email Queue recent rows readable | regression | `e2e/tests/ops/config.spec.ts` | automated |
| — | Daily Work Log Settings form opens | smoke | `e2e/tests/ops/config.spec.ts` | automated |

## Summary

| Module | Count | Smoke | Regression | Critical |
|--------|------:|------:|-----------:|---------:|
| HR | 59 | 1 | 21 | 37 |
| Accounts | 51 | 3 | 17 | 31 |
| Cross-module | 3 | 0 | 1 | 2 |
| Ops / Volunteering smoke | 15 | 12 | 2 | 0 |
| Volunteering gaps (VO-*) | 6 | 1 | 5 | 0 |
| **Spreadsheet total** | **113** | **4** | **39** | **70** |

