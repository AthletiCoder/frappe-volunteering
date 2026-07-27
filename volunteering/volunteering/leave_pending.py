# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Keep Employee.leave_approver aligned with reports_to (for list-filter inboxes)."""

from __future__ import annotations

import frappe


def sync_leave_approver_from_reports_to(doc=None, method=None):
	"""Keep Employee.leave_approver aligned with reports_to manager's user_id."""
	if isinstance(doc, str):
		doc = frappe.get_doc("Employee", doc)
	if not doc or not doc.reports_to:
		return

	manager_user = frappe.db.get_value("Employee", doc.reports_to, "user_id")
	if not manager_user:
		return

	if doc.leave_approver != manager_user:
		doc.leave_approver = manager_user


def backfill_leave_approvers_from_reports_to():
	"""One-shot / migrate: Employee + open Leave Applications follow reports_to."""
	updated_employees = 0
	employees = frappe.get_all(
		"Employee",
		filters={"status": "Active", "reports_to": ["is", "set"]},
		fields=["name", "reports_to", "leave_approver"],
	)
	for row in employees:
		manager_user = frappe.db.get_value("Employee", row.reports_to, "user_id")
		if not manager_user or row.leave_approver == manager_user:
			continue
		frappe.db.set_value("Employee", row.name, "leave_approver", manager_user, update_modified=False)
		updated_employees += 1
		if not frappe.db.exists("Has Role", {"parent": manager_user, "role": "Leave Approver"}):
			user = frappe.get_doc("User", manager_user)
			user.append("roles", {"role": "Leave Approver"})
			user.save(ignore_permissions=True)

	updated_apps = 0
	opens = frappe.get_all(
		"Leave Application",
		filters={"status": "Open", "docstatus": 0},
		fields=["name", "employee", "leave_approver"],
	)
	for app in opens:
		emp_approver = frappe.db.get_value("Employee", app.employee, "leave_approver")
		if emp_approver and app.leave_approver != emp_approver:
			frappe.db.set_value(
				"Leave Application",
				app.name,
				{
					"leave_approver": emp_approver,
					"leave_approver_name": frappe.db.get_value("User", emp_approver, "full_name"),
				},
				update_modified=False,
			)
			updated_apps += 1

	return {"updated_employees": updated_employees, "updated_apps": updated_apps}
