# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Advance portal APIs for Desk page + Frappe UI SPA."""

from __future__ import annotations

import base64
import binascii
import math
from pathlib import PurePath

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import cstr, flt, getdate, nowdate

from volunteering.volunteering.advance_freeze import direct_reports, freeze_status
from volunteering.volunteering.authority import get_employee_for_user
from volunteering.volunteering.employee_advance_controls import (
	advance_residual_amount,
	advance_residual_ratio,
)
from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details

MAX_FILE_BYTES = 5 * 1024 * 1024


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
			"intended_project",
			"required_by_date",
			"expected_settlement_date",
			"advance_use",
			"advance_additional_note",
			"advance_supporting_document",
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
				"route": f"/volunteering/advances/{row.name}",
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
		"intended_project": doc.get("intended_project"),
		"required_by_date": doc.get("required_by_date"),
		"expected_settlement_date": doc.get("expected_settlement_date"),
		"advance_use": doc.get("advance_use"),
		"advance_additional_note": doc.get("advance_additional_note"),
		"advance_supporting_document": doc.get("advance_supporting_document"),
	}
	residual = advance_residual_amount(row)
	return {
		**row,
		"residual": residual,
		"residual_pct": flt(advance_residual_ratio(row) * 100, 2),
		"route": f"/volunteering/advances/{doc.name}",
		"expense_claims": _claims_for_advance(doc.name),
		"new_expense_claim_url": (
			f"/volunteering/expense-claim?reimbursement_source=OWN_ADVANCE&employee_advance={doc.name}"
		),
		"new_advance_url": "/volunteering/advances?new=1",
	}


@frappe.whitelist(methods=["POST"])
def get_advance_request_form():
	"""Home-form defaults; all choices are scoped to the signed-in employee."""
	employee = _require_active_employee()
	values = frappe.db.get_value(
		"Employee",
		employee,
		["employee_name", "company", "department", "grade", "designation", "reports_to"],
		as_dict=True,
	)
	manager = (
		frappe.db.get_value("Employee", values.reports_to, ["employee_name", "user_id"], as_dict=True)
		if values.reports_to
		else None
	)
	from volunteering.volunteering.employee_advance_controls import (
		get_grade_advance_limit_for_employee,
		list_open_advances_for_employee,
	)

	bank = get_approved_bank_details(employee, reveal=False)
	return {
		"employee": employee,
		"employee_name": values.employee_name or employee,
		"grade": values.grade or values.designation,
		"department": values.department,
		"currency": frappe.db.get_value("Company", values.company, "default_currency") or "INR",
		"today": nowdate(),
		"projects": _eligible_projects(employee),
		"approved_bank": bank,
		"freeze": freeze_status(employee),
		"has_direct_reports": bool(direct_reports(employee)),
		"approver": {
			"name": manager.employee_name if manager else None,
			"user": manager.user_id if manager else None,
		},
		"limit": get_grade_advance_limit_for_employee(employee),
		"open_advances": [
			{
				"name": row.name,
				"status": row.status,
				"residual": flt(advance_residual_amount(row)),
			}
			for row in list_open_advances_for_employee(employee)
			if advance_residual_amount(row) > 0
		],
	}


@frappe.whitelist(methods=["POST"])
def save_advance_request(payload, submit_request=0):
	"""Create/update the employee's draft and optionally enter approval workflow."""
	employee = _require_active_employee()
	data = frappe.parse_json(payload)
	if not isinstance(data, dict):
		frappe.throw(_("Advance details must be a valid object."))
	allowed = {
		"name",
		"intended_project",
		"amount",
		"purpose",
		"required_by_date",
		"expected_settlement_date",
		"advance_use",
		"additional_note",
		"support_filename",
		"support_content",
	}
	if set(data) - allowed:
		frappe.throw(_("The advance request contains unsupported fields."))

	amount = flt(data.get("amount"), 2)
	if not math.isfinite(amount) or amount <= 0:
		frappe.throw(_("Enter a valid positive advance amount."))
	purpose = " ".join(cstr(data.get("purpose")).strip().split())
	if not purpose:
		frappe.throw(_("Purpose is required."))
	if len(purpose) > 500:
		frappe.throw(_("Purpose cannot exceed 500 characters."))
	note = cstr(data.get("additional_note")).strip()
	if len(note) > 1000:
		frappe.throw(_("Additional note cannot exceed 1,000 characters."))

	employee_values = frappe.db.get_value(
		"Employee", employee, ["employee_name", "company", "department"], as_dict=True
	)
	name = cstr(data.get("name")).strip()
	if name:
		doc = frappe.get_doc("Employee Advance", name)
		frappe.has_permission("Employee Advance", "write", name, throw=True)
		if (
			doc.employee != employee
			or doc.docstatus != 0
			or (doc.workflow_state or "Draft")
			not in (
				"Draft",
				"Rejected",
			)
		):
			frappe.throw(_("Only your own editable advance draft can be changed."), frappe.PermissionError)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Employee Advance",
				"employee": employee,
				"employee_name": employee_values.employee_name,
				"company": employee_values.company,
				"department": employee_values.department,
				"posting_date": nowdate(),
			}
		)

	doc.intended_project = cstr(data.get("intended_project")).strip()
	doc.advance_amount = amount
	doc.purpose = purpose
	doc.required_by_date = getdate(data.get("required_by_date") or nowdate())
	doc.expected_settlement_date = getdate(data.get("expected_settlement_date") or doc.required_by_date)
	doc.advance_use = cstr(data.get("advance_use") or "My expenses").strip()
	doc.advance_additional_note = note
	if doc.is_new():
		doc.insert()
	else:
		doc.save()

	if data.get("support_filename") or data.get("support_content"):
		file_doc = _attach_supporting_document(
			doc.name, data.get("support_filename"), data.get("support_content")
		)
		doc.advance_supporting_document = file_doc.file_url
		doc.save()

	if frappe.utils.cint(submit_request):
		action = "Re-submit" if doc.workflow_state == "Rejected" else "Submit"
		apply_workflow(doc, action)
		doc.reload()
	return {
		"name": doc.name,
		"workflow_state": doc.workflow_state,
		"status": doc.status,
		"submitted": bool(frappe.utils.cint(submit_request)),
	}


def _require_active_employee():
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Log in as an employee to request an advance."), frappe.PermissionError)
	employee = get_employee_for_user(frappe.session.user)
	if not employee or frappe.db.get_value("Employee", employee, "status") != "Active":
		frappe.throw(_("Your user must be linked to an active Employee record."), frappe.PermissionError)
	return employee


def _eligible_projects(employee):
	user = frappe.db.get_value("Employee", employee, "user_id")
	company = frappe.db.get_value("Employee", employee, "company")
	participants = frappe.get_all(
		"Project Participant",
		filters={"user": user, "parenttype": "Project", "parentfield": "project_participants"},
		pluck="parent",
	)
	owned = frappe.get_all("Project", filters={"project_owner": user}, pluck="name")
	names = list(dict.fromkeys([*owned, *participants]))
	if not names:
		return []
	rows = frappe.get_all(
		"Project",
		filters={
			"name": ["in", names],
			"company": company,
			"project_setup_version": [">", 0],
			"operational_status": "Active",
			"budget_status": ["!=", "Closed"],
			"is_archived": 0,
		},
		fields=["name", "project_name"],
		order_by="project_name asc",
	)
	return [
		{"value": row.name, "label": row.project_name or row.name, "description": row.name} for row in rows
	]


def _attach_supporting_document(advance_name, filename, encoded):
	filename = PurePath(cstr(filename)).name
	encoded = cstr(encoded)
	if not filename or len(encoded) > 7_000_000:
		frappe.throw(_("Attach a PDF, PNG or JPEG estimate/quotation no larger than 5 MB."))
	try:
		content = base64.b64decode(encoded, validate=True)
	except ValueError, binascii.Error:
		frappe.throw(_("The supporting document is invalid."))
	if not content or len(content) > MAX_FILE_BYTES:
		frappe.throw(_("The supporting document must be 5 MB or smaller."))
	extension = filename.rsplit(".", 1)[-1].lower()
	valid = (
		(extension == "pdf" and content.startswith(b"%PDF-"))
		or (extension == "png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
		or (extension in ("jpg", "jpeg") and content.startswith(b"\xff\xd8\xff"))
	)
	if not valid:
		frappe.throw(_("The supporting document must be a PDF, PNG or JPEG matching its extension."))
	return frappe.get_doc(
		{
			"doctype": "File",
			"file_name": filename,
			"content": content,
			"is_private": 1,
			"attached_to_doctype": "Employee Advance",
			"attached_to_name": advance_name,
			"attached_to_field": "advance_supporting_document",
		}
	).insert(ignore_permissions=True)


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
		"route": f"/volunteering/expense-claims?claim={ec.name}",
	}


def _resolve_employee(employee=None):
	roles = set(frappe.get_roles())
	accounts = roles.intersection(
		{"Accounts Manager", "Accounts User", "System Manager", "HR Manager", "HR User"}
	)
	if employee and accounts:
		return employee

	session_employee = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if not session_employee:
		frappe.throw(_("Your user is not linked to an Employee record."))
	if employee and employee != session_employee and not accounts:
		frappe.throw(_("You can only view your own advances."))
	return session_employee or employee
