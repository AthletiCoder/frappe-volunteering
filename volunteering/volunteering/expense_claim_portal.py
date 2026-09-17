# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee-facing Expense Claim submission service.

The portal deliberately exposes only project-approved expense-account labels and
the employee's own advances.  Company, employee, cost centre, payable account,
approval routing, sanctioned amounts and ledger fields remain server-controlled.
"""

from __future__ import annotations

import base64
import binascii
import math
from pathlib import PurePath

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import cint, cstr, flt, getdate, nowdate

from volunteering.volunteering.authority import get_employee_for_user
from volunteering.volunteering.employee_advance_controls import advance_residual_amount
from volunteering.volunteering.manager_float_service import (
	REIMBURSEMENT_MANAGER_ADVANCE,
	REIMBURSEMENT_OUT_OF_POCKET,
	list_fundable_manager_advances,
)

MAX_EXPENSES = 10
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_FILE_BYTES = 25 * 1024 * 1024
ALLOWED_SOURCE_VALUES = frozenset({"PERSONAL", "OWN_ADVANCE", "MANAGER_ADVANCE"})


@frappe.whitelist(methods=["POST"])
def get_expense_claim_form():
	employee = _require_employee()
	employee_values = frappe.db.get_value(
		"Employee",
		employee,
		["employee_name", "company", "department", "reports_to"],
		as_dict=True,
	)
	manager_employee = employee_values.reports_to
	manager = (
		frappe.db.get_value("Employee", manager_employee, ["employee_name", "user_id"], as_dict=True)
		if manager_employee
		else None
	)
	manager_advances = list_fundable_manager_advances(manager_employee, 0)
	return {
		"employee": employee,
		"employee_name": employee_values.employee_name or employee,
		"department": employee_values.department,
		"currency": frappe.db.get_value("Company", employee_values.company, "default_currency") or "INR",
		"expense_date": nowdate(),
		"projects": _claimable_projects(frappe.session.user),
		"own_advances": _own_advances(employee, employee_values.company),
		"manager_advance": {
			"available": bool(manager_advances),
			"manager_name": manager.employee_name if manager else None,
			"maximum_available": flt(manager_advances[0]["residual"]) if manager_advances else 0,
		},
		"approver": {
			"name": manager.employee_name if manager else None,
			"user": manager.user_id if manager else None,
		},
	}


@frappe.whitelist(methods=["POST"])
def get_project_accounts(project: str):
	employee = _require_employee()
	project_doc = _validate_claim_project(project, employee)
	return _account_options(project_doc)


@frappe.whitelist(methods=["POST"])
def submit_expense_claim(payload):
	"""Create a draft, attach private item evidence, then enter receipt review."""
	employee = _require_employee()
	data = frappe.parse_json(payload)
	if not isinstance(data, dict):
		frappe.throw(_("Expense claim details must be a valid object."))
	allowed = {
		"project",
		"purpose",
		"reimbursement_source",
		"employee_advance",
		"is_emergency",
		"emergency_date",
		"emergency_reason",
		"expenses",
	}
	if set(data) - allowed:
		frappe.throw(_("The expense claim contains unsupported fields."))

	project = _validate_claim_project(data.get("project"), employee)
	employee_values = frappe.db.get_value("Employee", employee, ["company", "department"], as_dict=True)
	if project.company != employee_values.company:
		frappe.throw(_("The selected Project belongs to a different Company."))
	accounts = {row["value"] for row in _account_options(project)}
	expenses, attachments, total = _normalise_expenses(data.get("expenses"), accounts)
	source = cstr(data.get("reimbursement_source") or "PERSONAL").strip().upper()
	if source not in ALLOWED_SOURCE_VALUES:
		frappe.throw(_("Choose a valid reimbursement source."))

	purpose = _text(data.get("purpose"), _("Claim purpose"), 500, required=True)
	is_emergency = cint(data.get("is_emergency"))
	emergency_reason = _text(data.get("emergency_reason"), _("Emergency reason"), 500)
	emergency_date = data.get("emergency_date")
	if is_emergency:
		if not emergency_reason:
			frappe.throw(
				_("Explain the emergency and why the normal prior-purchase process could not be followed.")
			)
		emergency_date = getdate(emergency_date or nowdate())
		if emergency_date > getdate(nowdate()):
			frappe.throw(_("Emergency date cannot be in the future."))

	company_currency = frappe.db.get_value("Company", employee_values.company, "default_currency") or "INR"
	doc = frappe.get_doc(
		{
			"doctype": "Expense Claim",
			"employee": employee,
			"company": employee_values.company,
			"department": employee_values.department,
			"project": project.name,
			"posting_date": nowdate(),
			"currency": company_currency,
			"exchange_rate": 1,
			"remark": purpose,
			"reimbursement_source": (
				REIMBURSEMENT_MANAGER_ADVANCE if source == "MANAGER_ADVANCE" else REIMBURSEMENT_OUT_OF_POCKET
			),
			"is_emergency": is_emergency,
			"emergency_date": emergency_date if is_emergency else None,
			"emergency_reason": emergency_reason if is_emergency else None,
			# Existing spend controls use this field to recognise an emergency
			# exception.  Keep its employee-facing text in the dedicated field.
			"vendor_override_reason": emergency_reason if is_emergency else None,
			"expenses": expenses,
		}
	)

	if source == "OWN_ADVANCE":
		_attach_own_advance(doc, data.get("employee_advance"), employee, total)
	elif data.get("employee_advance"):
		frappe.throw(_("An Employee Advance can only be selected for 'Against my advance'."))

	# Use normal document permission checks.  The service supplies internal
	# accounting values but never bypasses the employee's create permission.
	doc.insert()
	for index, file_data in attachments:
		file_doc = _attach_receipt(doc.name, index, file_data)
		row = doc.expenses[index]
		row.receipt_attachment = file_doc.file_url
	# Persist the per-item evidence association after File names/URLs exist.
	doc.save()
	apply_workflow(doc, "Submit")
	doc.reload()
	warnings = list(
		dict.fromkeys(
			cstr(message.get("message"))
			for message in frappe.local.message_log or []
			if isinstance(message, dict) and message.get("message")
		)
	)
	return {
		"name": doc.name,
		"workflow_state": doc.workflow_state,
		"receipt_review_status": doc.get("receipt_review_status"),
		"total": flt(doc.total_claimed_amount),
		"warnings": warnings,
	}


def _require_employee() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in as an employee to submit an expense claim."), frappe.PermissionError)
	employee = get_employee_for_user(user)
	if not employee or frappe.db.get_value("Employee", employee, "status") != "Active":
		frappe.throw(_("Your user must be linked to an active Employee record."), frappe.PermissionError)
	return employee


def _claimable_projects(user: str) -> list[dict]:
	projects = frappe.get_all(
		"Project Participant",
		filters={
			"user": user,
			"parenttype": "Project",
			"parentfield": "project_participants",
		},
		pluck="parent",
	)
	if not projects:
		return []
	rows = frappe.get_all(
		"Project",
		filters={
			"name": ["in", projects],
			"project_setup_version": [">", 0],
			"operational_status": "Active",
			"budget_status": ["!=", "Closed"],
			"is_archived": 0,
		},
		fields=["name", "project_name", "company"],
		order_by="project_name asc",
	)
	return [
		{
			"value": row.name,
			"label": row.project_name or row.name,
			"description": row.name,
		}
		for row in rows
		if frappe.db.exists(
			"Project Account Budget",
			{
				"parent": row.name,
				"parenttype": "Project",
				"parentfield": "account_budgets",
				"is_active": 1,
			},
		)
	]


def _validate_claim_project(project: str | None, employee: str):
	project = cstr(project).strip()
	if not project:
		frappe.throw(_("Select a Project."))
	doc = frappe.get_doc("Project", project)
	user = frappe.session.user
	if not cint(doc.get("project_setup_version")) or not any(
		row.user == user for row in doc.get("project_participants") or []
	):
		frappe.throw(
			_("You must be a listed member of this Project to submit bills."), frappe.PermissionError
		)
	if doc.operational_status != "Active":
		frappe.throw(_("New claims require an Active Project."))
	if doc.budget_status == "Closed" or cint(doc.get("is_archived")):
		frappe.throw(_("This Project is closed for new expense claims."))
	if doc.company != frappe.db.get_value("Employee", employee, "company"):
		frappe.throw(_("The selected Project belongs to a different Company."))
	return doc


def _account_options(project_doc) -> list[dict]:
	options = []
	for row in project_doc.get("account_budgets") or []:
		if not cint(row.is_active):
			continue
		account = frappe.db.get_value(
			"Account",
			row.expense_account,
			["name", "account_name", "company", "root_type", "is_group", "disabled"],
			as_dict=True,
		)
		if (
			not account
			or account.company != project_doc.company
			or account.root_type != "Expense"
			or cint(account.is_group)
			or cint(account.disabled)
		):
			continue
		friendly = cstr(row.employee_label).strip() or account.account_name or account.name
		options.append(
			{
				"value": account.name,
				"label": friendly,
				"description": account.name if friendly != account.name else "",
			}
		)
	return options


def _own_advances(employee: str, company: str) -> list[dict]:
	rows = frappe.get_all(
		"Employee Advance",
		filters={
			"employee": employee,
			"company": company,
			"docstatus": 1,
			"paid_amount": [">", 0],
		},
		fields=[
			"name",
			"purpose",
			"posting_date",
			"advance_amount",
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"status",
			"currency",
		],
		order_by="posting_date desc, creation desc",
	)
	return [
		{
			"name": row.name,
			"purpose": row.purpose,
			"posting_date": row.posting_date,
			"residual": flt(advance_residual_amount(row)),
			"currency": row.currency,
		}
		for row in rows
		if advance_residual_amount(row) > 0
	]


def _normalise_expenses(expenses, allowed_accounts: set[str]):
	if not isinstance(expenses, list) or not expenses:
		frappe.throw(_("Add at least one expense item."))
	if len(expenses) > MAX_EXPENSES:
		frappe.throw(_("Add at most {0} expense items to one claim.").format(MAX_EXPENSES))
	rows = []
	attachments = []
	total = 0.0
	total_file_bytes = 0
	for index, item in enumerate(expenses):
		if not isinstance(item, dict):
			frappe.throw(_("Expense item {0} is invalid.").format(index + 1))
		allowed = {
			"expense_date",
			"account",
			"supplier_name",
			"invoice_number",
			"description",
			"amount",
			"receipt_filename",
			"receipt_content",
		}
		if set(item) - allowed:
			frappe.throw(_("Expense item {0} contains unsupported fields.").format(index + 1))
		account = cstr(item.get("account")).strip()
		if account not in allowed_accounts:
			frappe.throw(
				_("Expense item {0} uses an account that is not available for this Project.").format(
					index + 1
				),
				frappe.PermissionError,
			)
		date = getdate(item.get("expense_date") or nowdate())
		if date > getdate(nowdate()):
			frappe.throw(_("Expense item {0} cannot use a future date.").format(index + 1))
		amount = flt(item.get("amount"), 2)
		if not math.isfinite(amount) or amount <= 0 or amount > 999_999_999:
			frappe.throw(_("Enter a valid positive amount for expense item {0}.").format(index + 1))
		file_data = _receipt(item, index + 1)
		total_file_bytes += len(file_data[1])
		if total_file_bytes > MAX_TOTAL_FILE_BYTES:
			frappe.throw(_("The combined receipt files must be 25 MB or smaller."))
		rows.append(
			{
				"expense_date": date,
				"project_expense_account": account,
				"description": _text(item.get("description"), _("Description"), 1000, required=True),
				"supplier_name": _text(item.get("supplier_name"), _("Supplier / payee"), 160),
				"supplier_invoice_number": _text(
					item.get("invoice_number"), _("Receipt / invoice number"), 100
				),
				"amount": amount,
				# Manager may reduce this later.  Initial equality lets advance
				# allocation and totals validate while the claim is still a draft.
				"sanctioned_amount": amount,
				"exchange_rate": 1,
			}
		)
		attachments.append((index, file_data))
		total += amount
	return rows, attachments, flt(total, 2)


def _receipt(item: dict, row_number: int) -> tuple[str, bytes]:
	filename = PurePath(cstr(item.get("receipt_filename")).strip()).name
	encoded = cstr(item.get("receipt_content")).strip()
	if not filename or not encoded:
		frappe.throw(_("Attach receipt evidence for expense item {0}.").format(row_number))
	if len(encoded) > 7_000_000:
		frappe.throw(_("Receipt for expense item {0} must be 5 MB or smaller.").format(row_number))
	try:
		content = base64.b64decode(encoded, validate=True)
	except ValueError, binascii.Error:
		frappe.throw(_("Receipt for expense item {0} is invalid.").format(row_number))
	if not content or len(content) > MAX_FILE_BYTES:
		frappe.throw(_("Receipt for expense item {0} must be 5 MB or smaller.").format(row_number))
	extension = PurePath(filename).suffix.lower()
	valid = (
		(extension == ".pdf" and content.startswith(b"%PDF-"))
		or (extension == ".png" and content.startswith(b"\x89PNG\r\n\x1a\n"))
		or (extension in (".jpg", ".jpeg") and content.startswith(b"\xff\xd8\xff"))
	)
	if not valid:
		frappe.throw(
			_("Receipt for expense item {0} must be a PDF, PNG or JPEG matching its extension.").format(
				row_number
			)
		)
	return filename, content


def _attach_receipt(claim_name: str, index: int, file_data: tuple[str, bytes]):
	filename, content = file_data
	return frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"item-{index + 1}-{filename}",
			"attached_to_doctype": "Expense Claim",
			"attached_to_name": claim_name,
			"content": content,
			"is_private": 1,
		}
	).insert(ignore_permissions=True)


def _attach_own_advance(doc, advance_name: str | None, employee: str, total: float):
	advance_name = cstr(advance_name).strip()
	if not advance_name:
		frappe.throw(_("Select the advance that these expenses should settle."))
	advance = frappe.get_doc("Employee Advance", advance_name)
	if advance.employee != employee or advance.company != doc.company:
		frappe.throw(_("You can only settle your own advance."), frappe.PermissionError)
	if advance.docstatus != 1 or flt(advance.paid_amount) <= 0:
		frappe.throw(_("The selected advance has not been submitted and paid."))
	residual = advance_residual_amount(advance)
	if residual <= 0:
		frappe.throw(_("The selected advance has no unsettled amount."))
	if advance.currency and advance.currency != doc.currency:
		frappe.throw(_("The selected advance uses a different currency."))

	from hrms.hr.doctype.expense_claim.expense_claim import get_expense_claim_advances

	get_expense_claim_advances(doc, advance)
	remaining = total
	kept = []
	for row in doc.advances:
		available = max(flt(row.unclaimed_amount) - flt(row.return_amount), 0)
		row.allocated_amount = min(available, remaining)
		remaining -= row.allocated_amount
		if row.allocated_amount > 0:
			kept.append(row)
	doc.set("advances", kept)
	if not kept:
		frappe.throw(_("No paid balance is available on the selected advance."))


def _text(value, label: str, maximum: int, required: bool = False) -> str:
	value = " ".join(cstr(value).strip().split())
	if required and not value:
		frappe.throw(_("{0} is required.").format(label))
	if len(value) > maximum:
		frappe.throw(_("{0} cannot exceed {1} characters.").format(label, maximum))
	return value
