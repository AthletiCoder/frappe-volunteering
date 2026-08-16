"""Employment type helpers for payroll vs unpaid staff."""

from __future__ import annotations

import frappe

UNPAID_EMPLOYMENT_TYPE = "Unpaid"


def ensure_employment_type(name: str = UNPAID_EMPLOYMENT_TYPE) -> str:
	"""Ensure Employment Type master exists; return its name."""
	if not frappe.db.exists("DocType", "Employment Type"):
		return name

	if frappe.db.exists("Employment Type", name):
		return name

	frappe.get_doc(
		{
			"doctype": "Employment Type",
			"employee_type_name": name,
		}
	).insert(ignore_permissions=True)
	return name


def is_unpaid_employee(employee: str | None) -> bool:
	if not employee:
		return False
	employment_type = frappe.db.get_value("Employee", employee, "employment_type") or ""
	return employment_type == UNPAID_EMPLOYMENT_TYPE or employment_type.lower().startswith("unpaid")


def is_payroll_employee(employee: str | None) -> bool:
	return bool(employee) and not is_unpaid_employee(employee)
