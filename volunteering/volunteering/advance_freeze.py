"""Append-only controls for temporarily blocking new employee advances."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe import _
from frappe.utils import cstr, now_datetime

DOCTYPE = "Employee Advance Freeze Event"
_freeze_mutation = ContextVar("employee_advance_freeze_mutation", default=False)


@contextmanager
def freeze_mutation():
	token = _freeze_mutation.set(True)
	try:
		yield
	finally:
		_freeze_mutation.reset(token)


def freeze_mutation_allowed() -> bool:
	return _freeze_mutation.get()


def employee_for_user(user=None, required=True):
	user = user or frappe.session.user
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if employee and frappe.db.get_value("Employee", employee, "status") != "Active":
		employee = None
	if required and not employee:
		frappe.throw(_("Your user must be linked to an active Employee record."), frappe.PermissionError)
	return employee


def is_direct_report(manager_employee, employee) -> bool:
	return bool(
		manager_employee
		and employee
		and frappe.db.get_value("Employee", employee, "reports_to") == manager_employee
	)


def direct_reports(manager_employee, active_only=True):
	filters = {"reports_to": manager_employee}
	if active_only:
		filters["status"] = "Active"
	return frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"user_id",
			"designation",
			"department",
			"grade",
			"status",
			"date_of_joining",
		],
		order_by="employee_name asc",
	)


def latest_freeze_event(employee):
	if not frappe.db.exists("DocType", DOCTYPE):
		return None
	rows = frappe.get_all(
		DOCTYPE,
		filters={"employee": employee},
		fields=["name", "action", "reason", "acted_by", "acted_on", "manager_employee"],
		order_by="acted_on desc, creation desc",
		limit=1,
	)
	return rows[0] if rows else None


def freeze_status(employee):
	event = latest_freeze_event(employee)
	return {
		"frozen": bool(event and event.action == "Freeze"),
		"reason": event.reason if event else "",
		"acted_by": event.acted_by if event else "",
		"acted_on": str(event.acted_on) if event and event.acted_on else "",
	}


def validate_not_frozen(employee):
	status = freeze_status(employee)
	if status["frozen"]:
		frappe.throw(
			_(
				"New advance requests are frozen for this employee. Contact your reporting manager. Reason: {0}"
			).format(status["reason"]),
			title=_("Advances Frozen"),
		)


@frappe.whitelist(methods=["POST"])
def set_advance_freeze(employee, frozen, reason):
	manager_employee = employee_for_user()
	if not is_direct_report(manager_employee, employee):
		frappe.throw(_("You can only change advance controls for a direct report."), frappe.PermissionError)
	reason = " ".join(cstr(reason).strip().split())
	if not reason:
		frappe.throw(_("Enter a reason for freezing or unfreezing advances."))
	if len(reason) > 500:
		frappe.throw(_("The freeze reason cannot exceed 500 characters."))

	desired_action = "Freeze" if frappe.utils.cint(frozen) else "Unfreeze"
	current = freeze_status(employee)
	if current["frozen"] == (desired_action == "Freeze"):
		frappe.throw(_("Advances are already {0} for this employee.").format(desired_action.lower() + "d"))

	doc = frappe.get_doc(
		{
			"doctype": DOCTYPE,
			"employee": employee,
			"action": desired_action,
			"reason": reason,
			"acted_by": frappe.session.user,
			"acted_on": now_datetime(),
			"manager_employee": manager_employee,
		}
	)
	with freeze_mutation():
		doc.insert(ignore_permissions=True)
	return freeze_status(employee)
