"""Cancel duplicate Privilege Leave allocations and re-assign earned leave policy.

Idempotent: employees already on a single modest allocation are skipped.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt, getdate

from volunteering.volunteering.employment_type import UNPAID_EMPLOYMENT_TYPE, ensure_employment_type
from volunteering.volunteering.leave_setup import (
	ANNUAL_LEAVE_ALLOCATION,
	LEAVE_TYPE_NAME,
	assign_leave_policy_to_employee,
	get_setup_settings,
	setup_hr_masters,
)

# Duplicate full-year grants typically sum to ~60; treat >= 1.5x annual as suspect.
DUPLICATE_ALLOCATION_THRESHOLD = ANNUAL_LEAVE_ALLOCATION * 1.5


def execute():
	ensure_employment_type()
	try:
		setup_hr_masters()
	except Exception:
		frappe.log_error(
			title="Leave masters setup failed during PL cleanup",
			message=frappe.get_traceback(),
		)

	settings = get_setup_settings()
	leave_period = settings.get("default_leave_period")
	if not leave_period:
		frappe.logger("volunteering").info("No default leave period; skipping PL cleanup")
		return

	period = frappe.db.get_value(
		"Leave Period", leave_period, ["from_date", "to_date"], as_dict=True
	)
	if not period or not period.from_date or not period.to_date:
		return

	from_date = getdate(period.from_date)
	to_date = getdate(period.to_date)

	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employment_type", "employee_name"],
	)

	summary = {"checked": 0, "fixed": 0, "skipped": 0, "errors": 0}
	for emp in employees:
		if emp.employment_type == UNPAID_EMPLOYMENT_TYPE:
			summary["skipped"] += 1
			continue
		summary["checked"] += 1
		try:
			if _fix_employee_allocations(emp.name, from_date, to_date, leave_period):
				summary["fixed"] += 1
		except Exception:
			summary["errors"] += 1
			frappe.log_error(
				title=f"Privilege Leave cleanup failed for {emp.name}",
				message=frappe.get_traceback(),
			)

	frappe.logger("volunteering").info(f"Privilege Leave cleanup: {summary}")


def _fix_employee_allocations(employee, from_date, to_date, leave_period) -> bool:
	allocations = frappe.get_all(
		"Leave Allocation",
		filters={
			"employee": employee,
			"leave_type": LEAVE_TYPE_NAME,
			"docstatus": 1,
			"from_date": ["<=", to_date],
			"to_date": [">=", from_date],
		},
		fields=[
			"name",
			"new_leaves_allocated",
			"total_leaves_allocated",
			"leave_policy_assignment",
			"creation",
		],
		order_by="creation asc",
	)

	if not allocations:
		return False

	total_new = sum(flt(row.new_leaves_allocated) for row in allocations)
	total_leaves = sum(flt(row.total_leaves_allocated) for row in allocations)
	needs_fix = len(allocations) > 1 or total_new >= DUPLICATE_ALLOCATION_THRESHOLD or total_leaves >= DUPLICATE_ALLOCATION_THRESHOLD

	if not needs_fix:
		return False

	frappe.logger("volunteering").info(
		f"Fixing PL for {employee}: {len(allocations)} allocation(s), "
		f"new={total_new}, total={total_leaves}"
	)

	assignment_names = {
		row.leave_policy_assignment for row in allocations if row.leave_policy_assignment
	}

	for row in allocations:
		_cancel_doc("Leave Allocation", row.name)

	for assignment_name in assignment_names:
		_cancel_doc("Leave Policy Assignment", assignment_name)

	# Also cancel any other submitted policy assignments overlapping this period
	# so assign_leave_policy_to_employee can create a fresh one.
	overlapping = frappe.get_all(
		"Leave Policy Assignment",
		filters={
			"employee": employee,
			"docstatus": 1,
			"effective_from": ["<=", to_date],
			"effective_to": [">=", from_date],
		},
		pluck="name",
	)
	for name in overlapping:
		_cancel_doc("Leave Policy Assignment", name)

	assign_leave_policy_to_employee(employee)
	return True


def _cancel_doc(doctype: str, name: str) -> None:
	if not name or not frappe.db.exists(doctype, name):
		return
	doc = frappe.get_doc(doctype, name)
	if doc.docstatus != 1:
		return
	doc.cancel()
