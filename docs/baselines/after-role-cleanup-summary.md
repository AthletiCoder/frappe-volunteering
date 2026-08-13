# AFTER baseline — meaningful fixes applied

Date: 2026-08-13  
Site: `sevamrita.local`

## Result

`bench --site sevamrita.local run-tests --app volunteering`

**Ran 157 — OK (0 FAIL, 0 ERROR)**

## Meaningful fixes (volunteering only)

1. **Emergency leave max days** — Policy is *calendar consecutive days*, not HRMS working-day leave count (weekends were making a 4-day span count as 3).
2. **Daily attendance** — Job correctly skips Unpaid; attendance tests now use a Full-time employee so they exercise the job path.
3. **Workflow PDF emails** — Accounting workflow states set `send_email: 0` so Frappe does not call `wkhtmltopdf` on every state change. Approvers still get link emails from `notify_pending_approvers` (no PDF attachment).
4. Removed stray debug logging / duplicate `_is_hr_user` in `leave_policy.py`.
5. Attendance tests restore `backdate_limit_days` after run (no site setting leak).
