# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Advance portal APIs for Desk page + Frappe UI SPA."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.desk_routes import desk_route
from volunteering.volunteering.employee_advance_controls import (
	advance_residual_amount,
	advance_residual_ratio,
)


@frappe.whitelist()
def get_my_advances(employee=None):
	"""List advances for the current employee (or Accounts-selected employee)."""
	employee = _resolve_employee(employee)
	rows = frappe.get_all(
		"Employee Advance",
		filters={"employee": employee, "docstatus": ["!=", 2]},
		fields=[
			"name",
			"employee",
			"employee_name",
			"status",
			"workflow_state",
			"advance_amount",
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"purpose",
			"posting_date",
			"company",
			"docstatus",
		],
		order_by="posting_date desc, creation desc",
	)
	out = []
	for row in rows:
		residual = advance_residual_amount(row)
		out.append(
			{
				**row,
				"residual": residual,
				"residual_pct": flt(advance_residual_ratio(row) * 100, 2),
				"route": desk_route("Employee Advance", row.name),
				"expense_claims": _claims_for_advance(row.name),
			}
		)
	return {"employee": employee, "advances": out}


@frappe.whitelist()
def get_advance_detail(name):
	frappe.has_permission("Employee Advance", "read", name, throw=True)
	doc = frappe.get_doc("Employee Advance", name)
	row = {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name,
		"status": doc.status,
		"workflow_state": doc.get("workflow_state"),
		"advance_amount": doc.advance_amount,
		"paid_amount": doc.paid_amount,
		"claimed_amount": doc.claimed_amount,
		"return_amount": doc.return_amount,
		"purpose": doc.purpose,
		"posting_date": doc.posting_date,
		"company": doc.company,
		"docstatus": doc.docstatus,
	}
	residual = advance_residual_amount(row)
	return {
		**row,
		"residual": residual,
		"residual_pct": flt(advance_residual_ratio(row) * 100, 2),
		"route": desk_route("Employee Advance", doc.name),
		"expense_claims": _claims_for_advance(doc.name),
		"new_expense_claim_url": (
			f"/app/expense-claim/new?employee={doc.employee}"
			f"&company={doc.company or ''}"
		),
		"new_advance_url": "/app/employee-advance/new",
	}


def _claims_for_advance(advance_name):
	"""Expense Claims linked via advances child table or manager_float_advance."""
	seen = set()
	out = []

	if frappe.db.exists("DocType", "Expense Claim Advance"):
		links = frappe.get_all(
			"Expense Claim Advance",
			filters={"employee_advance": advance_name},
			fields=["parent", "allocated_amount"],
		)
		for link in links:
			seen.add(link.parent)
			row = _claim_row(link.parent, link.allocated_amount)
			if row:
				out.append(row)

	if frappe.db.has_column("Expense Claim", "manager_float_advance"):
		for name in frappe.get_all(
			"Expense Claim",
			filters={"manager_float_advance": advance_name, "docstatus": ["!=", 2]},
			pluck="name",
		):
			if name in seen:
				continue
			seen.add(name)
			amount = frappe.db.get_value(
				"Expense Claim",
				name,
				"total_sanctioned_amount",
			) or frappe.db.get_value("Expense Claim", name, "total_claimed_amount")
			row = _claim_row(name, amount)
			if row:
				out.append(row)

	return out


def _claim_row(name, allocated_amount):
	ec = frappe.db.get_value(
		"Expense Claim",
		name,
		[
			"name",
			"employee",
			"status",
			"approval_status",
			"workflow_state",
			"total_claimed_amount",
			"total_sanctioned_amount",
			"posting_date",
			"docstatus",
			"reimbursement_source",
		],
		as_dict=True,
	)
	if not ec:
		return None
	return {
		**ec,
		"allocated_amount": allocated_amount,
		"route": desk_route("Expense Claim", ec.name),
	}


def _resolve_employee(employee=None):
	roles = set(frappe.get_roles())
	accounts = roles.intersection(
		{"Accounts Manager", "Accounts User", "System Manager", "HR Manager", "HR User"}
	)
	if employee and accounts:
		return employee

	session_employee = frappe.db.get_value(
		"Employee", {"user_id": frappe.session.user}, "name"
	)
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))
	if employee and employee != session_employee and not accounts:
		frappe.throw(_("You can only view your own advances."))
	return session_employee or employee
