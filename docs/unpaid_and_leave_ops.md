"""Ops note: Unpaid employment type and leave remediation.

## Unpaid Employment Type

1. After deploy/migrate, Employment Type **Unpaid** is created automatically.
2. On each unpaid staff member's Employee record, set **Employment Type = Unpaid**.
3. Effects:
   - Excluded from nightly auto attendance (Present/Absent)
   - Excluded from default Privilege Leave policy assignment
   - Excluded from the Executive Board attendance digest
4. They can still use Desk manually (work logs, leave applications) if roles allow;
   automation simply does not treat them as payroll staff.

## Leave balance showing ~60 (old policy)

Privilege Leave is earned monthly (~2.5/month, max 30/year) via
**Sevamrita Standard Leave Policy**.

Balances near **60** usually mean duplicate overlapping Leave Allocations
(old full-year grant + current policy).

The migrate patch `fix_duplicate_privilege_leave_allocations` cancels
obsolete duplicate Privilege Leave allocations in the current leave period
and re-assigns the standard leave policy so HRMS earned accrual applies.

### Manual fallback (per employee)

1. Open **Leave Allocation** for Privilege Leave; cancel the extra/old
   submitted allocation(s) that double-count the year.
2. Ensure a single submitted **Leave Policy Assignment** for the current
   leave period (Sevamrita Standard Leave Policy).
3. If needed, cancel and re-submit the Leave Policy Assignment so earned
   leave is recalculated from date of joining.
4. Confirm balance on Employee Leave Balance / Leave Application.
"""
