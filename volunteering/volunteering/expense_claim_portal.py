# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee-facing Expense Claim submission service.

The portal deliberately exposes only project-approved expense-category labels and
the employee's own advances.  Company, employee, cost centre, payable account,
approval routing, sanctioned amounts and ledger fields remain server-controlled.
"""

from __future__ import annotations

import base64
import binascii
import json
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


def _claim_stage(row) -> str:
	"""Return a stable, employee-facing status bucket."""
	workflow_state = cstr(row.get("workflow_state") or "Draft")
	status = cstr(row.get("status"))
	if cint(row.get("docstatus")) == 2 or status == "Cancelled":
		return "Cancelled"
	if cint(row.get("is_paid")) or status == "Paid":
		return "Paid"
	if workflow_state == "Pending Receipt Review":
		return "Receipt review"
	if workflow_state == "Receipt Correction Required":
		return "Needs correction"
	if workflow_state == "Pending Approval":
		return "Manager approval"
	if workflow_state == "Rejected" or row.get("approval_status") == "Rejected":
		return "Rejected"
	if workflow_state == "Approved" or row.get("approval_status") == "Approved":
		return "Approved / unpaid"
	return "Draft"


def _next_claim_action(row) -> str:
	stage = _claim_stage(row)
	return {
		"Draft": _("Complete and submit the claim"),
		"Needs correction": _("Correct the receipts and resubmit"),
		"Receipt review": _("Waiting for independent receipt review"),
		"Manager approval": _("Waiting for manager approval"),
		"Approved / unpaid": _("Waiting for Accounts to reimburse or settle it"),
		"Rejected": _("Review the decision before resubmitting"),
		"Paid": _("Complete"),
		"Cancelled": _("Closed"),
	}.get(stage, stage)


def _claim_source(doc) -> str:
	if doc.get("manager_float_advance") or doc.get("reimbursement_source") == REIMBURSEMENT_MANAGER_ADVANCE:
		return _("Against manager's advance")
	if doc.get("advances"):
		return _("Against my advance")
	return _("Paid personally")


def _project_names(projects) -> dict[str, str]:
	projects = sorted({cstr(project) for project in projects if project})
	if not projects:
		return {}
	return {
		row.name: row.project_name or row.name
		for row in frappe.get_all(
			"Project",
			filters={"name": ["in", projects]},
			fields=["name", "project_name"],
			limit=500,
		)
	}


def _claim_summary(row, project_names=None) -> dict:
	project_names = project_names or {}
	claimed = flt(row.get("total_claimed_amount"), 2)
	sanctioned = flt(row.get("total_sanctioned_amount"), 2)
	reimbursed = flt(row.get("total_amount_reimbursed"), 2)
	stage = _claim_stage(row)
	return {
		"name": row.name,
		"posting_date": row.posting_date,
		"creation": row.creation,
		"modified": row.modified,
		"project": row.project,
		"project_name": project_names.get(row.project) or row.project,
		"purpose": row.get("remark") or "",
		"currency": row.get("currency") or "INR",
		"claimed_amount": claimed,
		"sanctioned_amount": sanctioned,
		"reimbursed_amount": reimbursed,
		"outstanding_amount": max((sanctioned or claimed) - reimbursed, 0),
		"workflow_state": row.get("workflow_state") or "Draft",
		"receipt_review_status": row.get("receipt_review_status") or "Not Submitted",
		"approval_status": row.get("approval_status") or "Draft",
		"payment_status": "Paid" if stage == "Paid" else row.get("status") or "Unpaid",
		"stage": stage,
		"next_action": _next_claim_action(row),
		"docstatus": cint(row.get("docstatus")),
	}


@frappe.whitelist(methods=["POST"])
def get_my_expense_claims():
	"""Employee-safe list of every claim belonging to the signed-in employee."""
	employee = _require_employee()
	rows = frappe.get_all(
		"Expense Claim",
		filters={"employee": employee},
		fields=[
			"name",
			"posting_date",
			"creation",
			"modified",
			"project",
			"remark",
			"currency",
			"total_claimed_amount",
			"total_sanctioned_amount",
			"total_amount_reimbursed",
			"workflow_state",
			"receipt_review_status",
			"approval_status",
			"status",
			"is_paid",
			"docstatus",
		],
		order_by="posting_date desc, creation desc",
		limit=500,
	)
	projects = _project_names(row.project for row in rows)
	claims = [_claim_summary(row, projects) for row in rows]
	counts = {"All": len(claims)}
	for claim in claims:
		counts[claim["stage"]] = counts.get(claim["stage"], 0) + 1
	return {"employee": employee, "claims": claims, "counts": counts}


def _expense_labels(project: str | None) -> dict[str, str]:
	if not project:
		return {}
	return {
		row.budget_key: row.employee_label
		for row in frappe.get_all(
			"Project Account Budget",
			filters={
				"parent": project,
				"parenttype": "Project",
				"parentfield": "account_budgets",
			},
			fields=["budget_key", "employee_label"],
			limit=500,
		)
	}


def _workflow_timeline(doc) -> list[dict]:
	events = [
		{
			"label": _("Claim created"),
			"when": doc.creation,
			"by": doc.owner,
			"detail": _("Saved as an expense claim."),
		}
	]
	seen = set()
	for version in frappe.get_all(
		"Version",
		filters={"ref_doctype": "Expense Claim", "docname": doc.name},
		fields=["creation", "owner", "data"],
		order_by="creation asc",
		limit=200,
	):
		try:
			changes = json.loads(version.data or "{}").get("changed") or []
		except TypeError, ValueError:
			continue
		for change in changes:
			if len(change) < 3 or change[0] != "workflow_state":
				continue
			state = cstr(change[2])
			key = (state, str(version.creation))
			if not state or key in seen:
				continue
			seen.add(key)
			events.append(
				{
					"label": state,
					"when": version.creation,
					"by": version.owner,
					"detail": _("Workflow status changed."),
				}
			)
	if doc.get("receipt_reviewed_on"):
		events.append(
			{
				"label": _("Receipt review: {0}").format(doc.get("receipt_review_status") or _("Reviewed")),
				"when": doc.receipt_reviewed_on,
				"by": doc.get("receipt_reviewed_by") or "",
				"detail": doc.get("receipt_review_notes") or "",
			}
		)
	if doc.get("clearance_date"):
		events.append(
			{
				"label": _("Payment cleared"),
				"when": doc.clearance_date,
				"by": "",
				"detail": _("The claim was marked paid or settled."),
			}
		)
	return sorted(events, key=lambda event: str(event.get("when") or ""))


@frappe.whitelist(methods=["POST"])
def get_my_expense_claim(name: str):
	"""Employee-safe detail for one of the signed-in employee's claims."""
	employee = _require_employee()
	doc = frappe.get_doc("Expense Claim", cstr(name).strip())
	if doc.employee != employee:
		frappe.throw(_("You can only view your own expense claims."), frappe.PermissionError)
	projects = _project_names([doc.project])
	labels = _expense_labels(doc.project)
	summary = _claim_summary(doc, projects)
	summary.update(
		{
			"source": _claim_source(doc),
			"pending_with": (
				frappe.db.get_value("User", doc.get("pending_approver"), "full_name")
				if doc.get("pending_approver")
				else ""
			),
			"receipt_reviewed_by": doc.get("receipt_reviewed_by") or "",
			"receipt_reviewed_on": doc.get("receipt_reviewed_on"),
			"receipt_review_notes": doc.get("receipt_review_notes") or "",
			"clearance_date": doc.get("clearance_date"),
			"is_emergency": cint(doc.get("is_emergency")),
			"emergency_reason": doc.get("emergency_reason") or "",
			"expenses": [
				{
					"expense_date": row.expense_date,
					"category": labels.get(row.get("project_expense_account")) or _("Project expense"),
					"supplier_name": row.get("supplier_name") or "",
					"invoice_number": row.get("supplier_invoice_number") or "",
					"description": row.description or "",
					"amount": flt(row.amount, 2),
					"sanctioned_amount": flt(row.sanctioned_amount, 2),
					"receipt_attachment": row.get("receipt_attachment") or "",
				}
				for row in doc.expenses
			],
			"timeline": _workflow_timeline(doc),
		}
	)
	return summary


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

	# Older clients may still send a claim-level purpose. The employee portal no
	# longer asks for it because every line already requires a description and
	# business purpose. Use those descriptions as the claim summary instead.
	purpose = _text(data.get("purpose"), _("Claim purpose"), 500)
	if not purpose:
		purpose = " · ".join(dict.fromkeys(row["description"] for row in expenses))
		if len(purpose) > 500:
			purpose = purpose[:497].rstrip() + "..."
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
	from volunteering.volunteering.project_expense_accounts import employee_options

	return employee_options(project_doc)


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
