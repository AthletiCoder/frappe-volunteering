# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Permission-scoped Home services for advance approval and settlement."""

from __future__ import annotations

import math
from copy import deepcopy

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import cint, cstr, flt, getdate, nowdate

from volunteering.volunteering.advance_portal import _claims_for_advance
from volunteering.volunteering.approval_routing import (
	escalate_document,
	get_approver_action_flags,
)
from volunteering.volunteering.employee_advance_controls import advance_residual_amount
from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details

HOME_ROUTE = "/volunteering/advance-workflow"
DISBURSEMENT_ROLES = frozenset({"Accounts Manager", "Accounts User"})


def _roles(user: str | None = None) -> set[str]:
	return set(frappe.get_roles(user or frappe.session.user))


def _is_accounts_user(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(_roles(user).intersection(DISBURSEMENT_ROLES))


def _can_approve(doc, user: str) -> bool:
	return (
		doc.docstatus == 0
		and doc.get("workflow_state") == "Pending Approval"
		and doc.get("pending_approver") == user
	)


def _outstanding_to_pay(doc) -> float:
	return max(flt(doc.get("advance_amount"), 2) - flt(doc.get("paid_amount"), 2), 0.0)


def _can_disburse(doc, user: str) -> bool:
	return (
		_is_accounts_user(user)
		and doc.docstatus == 1
		and doc.get("workflow_state") == "Approved"
		and _outstanding_to_pay(doc) > 0
	)


def _can_record_return(doc, user: str) -> bool:
	return (
		_is_accounts_user(user)
		and doc.docstatus == 1
		and doc.get("workflow_state") == "Approved"
		and flt(doc.get("paid_amount"), 2) > 0
		and flt(advance_residual_amount(doc), 2) > 0
	)


def _assert_work_access(doc) -> dict:
	user = frappe.session.user
	access = {
		"approval": _can_approve(doc, user),
		"disbursement": _can_disburse(doc, user),
		"return": _can_record_return(doc, user),
	}
	if not any(access.values()):
		frappe.throw(_("This advance is not awaiting an action from you."), frappe.PermissionError)
	return access


def _queue_row(row, kind: str) -> dict:
	return {
		"name": row.name,
		"kind": kind,
		"employee_name": row.employee_name or row.employee or row.name,
		"project": row.intended_project,
		"amount": flt(row.advance_amount, 2),
		"paid_amount": flt(row.paid_amount, 2),
		"residual_amount": flt(advance_residual_amount(row), 2) if kind == "return" else 0,
		"currency": row.currency or "INR",
		"required_by_date": row.required_by_date,
		"modified": row.modified,
		"route": f"{HOME_ROUTE}?advance={row.name}",
	}


@frappe.whitelist(methods=["POST"])
def get_advance_work_queue():
	"""Return only advances the signed-in user may decide or disburse."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to work with advances."), frappe.PermissionError)

	fields = [
		"name",
		"employee",
		"employee_name",
		"intended_project",
		"currency",
		"advance_amount",
		"paid_amount",
		"required_by_date",
		"modified",
	]
	queues = {"approval": [], "disbursement": [], "return": []}
	queues["approval"] = [
		_queue_row(row, "approval")
		for row in frappe.get_all(
			"Employee Advance",
			filters={
				"docstatus": 0,
				"workflow_state": "Pending Approval",
				"pending_approver": user,
			},
			fields=fields,
			order_by="modified asc",
			limit=200,
		)
	]
	if _is_accounts_user(user):
		rows = frappe.get_all(
			"Employee Advance",
			filters={"docstatus": 1, "workflow_state": "Approved"},
			fields=fields,
			order_by="required_by_date asc, modified asc",
			limit=500,
		)
		queues["disbursement"] = [
			_queue_row(row, "disbursement") for row in rows if _outstanding_to_pay(row) > 0
		]
		return_rows = frappe.get_all(
			"Employee Advance",
			filters={"docstatus": 1, "workflow_state": "Approved", "paid_amount": [">", 0]},
			fields=fields + ["claimed_amount", "return_amount", "status"],
			order_by="modified desc",
			limit=500,
		)
		queues["return"] = [
			_queue_row(row, "return")
			for row in return_rows
			if flt(advance_residual_amount(row), 2) > 0
		]

	return {
		"can_disburse": _is_accounts_user(user),
		"queues": queues,
		"counts": {key: len(value) for key, value in queues.items()},
	}


def _project_name(project: str | None) -> str:
	if not project:
		return ""
	return frappe.db.get_value("Project", project, "project_name") or project


def _payment_options(doc) -> dict | None:
	if not _can_disburse(doc, frappe.session.user):
		return None
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": doc.company,
			"is_group": 0,
			"disabled": 0,
			"account_type": ["in", ["Bank", "Cash"]],
			"account_currency": doc.currency,
		},
		fields=["name", "account_name", "account_type", "account_currency"],
		order_by="account_type asc, account_name asc",
		limit=500,
	)
	return {
		"accounts": [
			{
				"value": row.name,
				"label": row.account_name or row.name,
				"type": row.account_type,
				"currency": row.account_currency,
			}
			for row in accounts
		],
		"modes_of_payment": frappe.get_all(
			"Mode of Payment",
			filters={"enabled": 1},
			fields=["name", "type"],
			order_by="name asc",
			limit=200,
		),
		"approved_bank": get_approved_bank_details(doc.employee, reveal=False),
		"posting_date": nowdate(),
		"outstanding": _outstanding_to_pay(doc),
	}


def _return_options(doc) -> dict | None:
	if not _can_record_return(doc, frappe.session.user):
		return None
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": doc.company,
			"is_group": 0,
			"disabled": 0,
			"account_type": ["in", ["Bank", "Cash"]],
			"account_currency": doc.currency,
		},
		fields=["name", "account_name", "account_type"],
		order_by="account_type asc, account_name asc",
		limit=500,
	)
	return {
		"accounts": [
			{"value": row.name, "label": row.account_name or row.name, "type": row.account_type}
			for row in accounts
		],
		"posting_date": nowdate(),
		"maximum": flt(advance_residual_amount(doc), 2),
	}


def _pending_claim_names(advance_name: str) -> list[str]:
	return [
		row["name"]
		for row in _claims_for_advance(advance_name)
		if cint(row.get("docstatus")) == 0
		and row.get("workflow_state") not in ("Rejected", "Cancelled")
	]


@frappe.whitelist(methods=["POST"])
def get_advance_work_item(name: str):
	doc = frappe.get_doc("Employee Advance", cstr(name).strip())
	access = _assert_work_access(doc)
	flags = (
		get_approver_action_flags("Employee Advance", doc.name)
		if access["approval"]
		else {
			"is_pending_approver": False,
			"can_approve": False,
			"can_escalate": False,
			"can_reject": False,
		}
	)
	return {
		"name": doc.name,
		"employee": doc.employee,
		"employee_name": doc.employee_name or doc.employee,
		"project": doc.get("intended_project"),
		"project_name": _project_name(doc.get("intended_project")),
		"posting_date": doc.posting_date,
		"required_by_date": doc.get("required_by_date"),
		"expected_settlement_date": doc.get("expected_settlement_date"),
		"advance_use": doc.get("advance_use") or _("My expenses"),
		"additional_note": doc.get("advance_additional_note") or "",
		"supporting_document": doc.get("advance_supporting_document") or "",
		"purpose": doc.purpose or "",
		"currency": doc.currency or "INR",
		"workflow_state": doc.workflow_state,
		"status": doc.status,
		"requested_amount": flt(doc.advance_amount, 2),
		"paid_amount": flt(doc.paid_amount, 2),
		"claimed_amount": flt(doc.claimed_amount, 2),
		"returned_amount": flt(doc.return_amount, 2),
		"residual_amount": flt(advance_residual_amount(doc), 2),
		"outstanding_to_pay": _outstanding_to_pay(doc),
		"access": access,
		"approval_flags": flags,
		"payment": _payment_options(doc),
		"return_options": _return_options(doc),
		"pending_claims": _pending_claim_names(doc.name) if access["return"] else [],
		"expense_claims": _claims_for_advance(doc.name) if (access["disbursement"] or access["return"]) else [],
	}


@frappe.whitelist(methods=["POST"])
def decide_advance(name: str, action: str, reason: str = ""):
	"""Approve, reject or escalate without exposing editable accounting fields."""
	doc = frappe.get_doc("Employee Advance", cstr(name).strip())
	if not _can_approve(doc, frappe.session.user):
		frappe.throw(_("Only the current advance reviewer can decide this request."), frappe.PermissionError)
	action = cstr(action).strip().lower()
	reason = cstr(reason).strip()
	flags = get_approver_action_flags("Employee Advance", doc.name)

	if action == "escalate":
		if not flags.get("can_escalate"):
			frappe.throw(_("Your approval authority covers the live outstanding amount."))
		if not reason:
			frappe.throw(_("Give a reason for escalation."))
		escalate_document("Employee Advance", doc.name, reason)
		return {"name": doc.name, "action": "escalated"}

	if action == "reject":
		if not flags.get("can_reject"):
			frappe.throw(_("You cannot reject this advance."), frappe.PermissionError)
		if not reason:
			frappe.throw(_("Give a reason for rejection."))
		doc.add_comment("Comment", _("Advance rejected: {0}").format(reason))
		apply_workflow(doc, "Reject")
		return {"name": doc.name, "action": "rejected"}

	if action != "approve":
		frappe.throw(_("Choose Approve, Reject or Escalate."))
	if not flags.get("can_approve"):
		frappe.throw(_("This request exceeds your current authority and must be escalated."))
	if reason:
		doc.add_comment("Comment", _("Advance approval note: {0}").format(reason))
	apply_workflow(doc, "Approve")
	return {"name": doc.name, "action": "approved"}


def _validate_payment_account(company: str, currency: str, account: str):
	row = frappe.db.get_value(
		"Account",
		cstr(account).strip(),
		["name", "company", "account_type", "account_currency", "is_group", "disabled"],
		as_dict=True,
	)
	if (
		not row
		or row.company != company
		or row.account_type not in ("Bank", "Cash")
		or row.account_currency != currency
		or cint(row.is_group)
		or cint(row.disabled)
	):
		frappe.throw(_("Select an enabled Bank or Cash account in the advance currency."))
	return row


@frappe.whitelist(methods=["POST"])
def disburse_advance(name: str, payment=None):
	"""Create and submit a Payment Entry against an approved advance."""
	if not _is_accounts_user():
		frappe.throw(_("Accounts access is required to disburse an advance."), frappe.PermissionError)
	data = frappe.parse_json(payment) if isinstance(payment, str) else payment
	if not isinstance(data, dict):
		frappe.throw(_("Payment details are required."))
	allowed = {
		"amount",
		"paid_from",
		"mode_of_payment",
		"posting_date",
		"reference_no",
		"reference_date",
	}
	if set(data) - allowed:
		frappe.throw(_("The payment contains unsupported fields."))

	advance_name = cstr(name).strip()
	frappe.db.sql("SELECT name FROM `tabEmployee Advance` WHERE name=%s FOR UPDATE", advance_name)
	doc = frappe.get_doc("Employee Advance", advance_name)
	if not _can_disburse(doc, frappe.session.user):
		frappe.throw(_("This advance is not approved and awaiting disbursement."))
	outstanding = _outstanding_to_pay(doc)
	amount = flt(data.get("amount"), 2)
	if not math.isfinite(amount) or amount <= 0 or amount > outstanding:
		frappe.throw(
			_("Payment amount must be greater than zero and no more than {0}.").format(
				frappe.format_value(outstanding, {"fieldtype": "Currency", "options": doc.currency})
			)
		)
	account = _validate_payment_account(doc.company, doc.currency, data.get("paid_from"))
	posting_date = getdate(data.get("posting_date") or nowdate())
	if posting_date > getdate(nowdate()):
		frappe.throw(_("Payment posting date cannot be in the future."))

	from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

	# HRMS checks Desk read permission both while building and validating the
	# Payment Entry reference. This endpoint has already authorized the exact
	# approved advance and source ledger; execute the accounting transaction in
	# a narrowly scoped Administrator context, retaining the Accounts actor in
	# the Payment Entry remarks for audit.
	actor = frappe.session.user
	original_session = deepcopy(frappe.local.session)
	try:
		frappe.set_user("Administrator")
		pe = get_payment_entry_for_employee(
			"Employee Advance",
			doc.name,
			party_amount=amount,
			bank_account=account.name,
		)
		pe.posting_date = posting_date
		mode = cstr(data.get("mode_of_payment")).strip()
		if mode:
			mode_type = frappe.db.get_value(
				"Mode of Payment", {"name": mode, "enabled": 1}, "type"
			)
			if not mode_type or mode_type != account.account_type:
				frappe.throw(_("Choose an enabled Mode of Payment."))
			pe.mode_of_payment = mode

		if account.account_type == "Bank":
			approved = get_approved_bank_details(doc.employee, reveal=False)
			if not approved:
				frappe.throw(
					_("An Accounts Manager must approve this employee's bank details before bank payment.")
				)
			pe.party_bank_account = frappe.db.get_value(
				"Employee Bank Account Request", approved["request"], "bank_account"
			)
			pe.reference_no = cstr(data.get("reference_no")).strip()
			pe.reference_date = getdate(data.get("reference_date") or posting_date)
			if not pe.reference_no:
				frappe.throw(_("Transaction reference number is required for a bank payment."))
		else:
			pe.reference_no = None
			pe.reference_date = None

		pe.insert()
		pe.submit()
		comment = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Comment",
				"reference_doctype": "Payment Entry",
				"reference_name": pe.name,
				"content": _("Home advance disbursement authorized by {0}").format(actor),
			}
		).insert(ignore_permissions=True)
		frappe.db.set_value("Comment", comment.name, "owner", actor, update_modified=False)
	finally:
		frappe.set_user(actor)
		frappe.local.session.clear()
		frappe.local.session.update(original_session)
		session_obj = getattr(frappe.local, "session_obj", None)
		if session_obj:
			session_obj.data = frappe.local.session
	doc.reload()
	return {
		"advance": doc.name,
		"payment_entry": pe.name,
		"amount": amount,
		"status": doc.status,
		"paid_amount": flt(doc.paid_amount, 2),
		"outstanding": _outstanding_to_pay(doc),
		"paid_from": pe.paid_from,
	}


@frappe.whitelist(methods=["POST"])
def record_advance_return(name: str, details=None):
	"""Accounts records funds actually received back against a paid advance."""
	if not _is_accounts_user():
		frappe.throw(_("Accounts access is required to record an advance return."), frappe.PermissionError)
	data = frappe.parse_json(details) if isinstance(details, str) else details
	if not isinstance(data, dict):
		frappe.throw(_("Return details are required."))
	allowed = {"amount", "received_into", "posting_date", "reference_no", "reference_date"}
	if set(data) - allowed:
		frappe.throw(_("The return contains unsupported fields."))

	advance_name = cstr(name).strip()
	frappe.db.sql("SELECT name FROM `tabEmployee Advance` WHERE name=%s FOR UPDATE", advance_name)
	doc = frappe.get_doc("Employee Advance", advance_name)
	if not _can_record_return(doc, frappe.session.user):
		frappe.throw(_("This advance has no paid, unclaimed balance available to return."))
	if _pending_claim_names(doc.name):
		frappe.throw(_("Resolve claims awaiting review or approval against this advance before recording a return."))
	maximum = flt(advance_residual_amount(doc), 2)
	amount = flt(data.get("amount"), 2)
	if not math.isfinite(amount) or amount <= 0 or amount > maximum:
		frappe.throw(_("Return amount must be greater than zero and no more than {0}.").format(maximum))
	account = _validate_payment_account(doc.company, doc.currency, data.get("received_into"))
	posting_date = getdate(data.get("posting_date") or nowdate())
	if posting_date > getdate(nowdate()):
		frappe.throw(_("Return posting date cannot be in the future."))
	company_currency = frappe.db.get_value("Company", doc.company, "default_currency")
	advance_account = frappe.db.get_value(
		"Account",
		doc.advance_account,
		["name", "company", "account_type", "account_currency", "is_group", "disabled"],
		as_dict=True,
	)
	if (
		company_currency != doc.currency
		or not advance_account
		or advance_account.company != doc.company
		or advance_account.account_type not in ("Receivable", "Payable")
		or advance_account.account_currency != doc.currency
		or cint(advance_account.is_group)
		or cint(advance_account.disabled)
	):
		frappe.throw(_("The advance account and return ledger must be active accounts in the company currency."))

	reference_no = cstr(data.get("reference_no")).strip()
	reference_date = getdate(data.get("reference_date") or posting_date)
	if account.account_type == "Bank":
		if not reference_no:
			frappe.throw(_("Bank receipt reference number is required."))
		if reference_date > getdate(nowdate()):
			frappe.throw(_("Bank receipt reference date cannot be in the future."))
	else:
		reference_no = ""
		reference_date = None

	from erpnext import get_default_cost_center

	actor = frappe.session.user
	original_session = deepcopy(frappe.local.session)
	previous_return = flt(doc.return_amount, 2)
	try:
		# The Accounts actor has been authorized for this exact advance and ledger.
		# Journal Entry validation may require additional Desk permissions.
		frappe.set_user("Administrator")
		je = frappe.get_doc(
			{
				"doctype": "Journal Entry",
				"company": doc.company,
				"posting_date": posting_date,
				"voucher_type": "Bank Entry" if account.account_type == "Bank" else "Cash Entry",
				"cheque_no": reference_no or None,
				"cheque_date": reference_date,
				"remark": _("Return against Employee Advance {0}; recorded by {1}").format(doc.name, actor),
			}
		)
		je.append(
			"accounts",
			{
				"account": doc.advance_account,
				"credit_in_account_currency": amount,
				"reference_type": "Employee Advance",
				"reference_name": doc.name,
				"party_type": "Employee",
				"party": doc.employee,
				"is_advance": "Yes",
				"cost_center": get_default_cost_center(doc.company),
			},
		)
		je.append(
			"accounts",
			{
				"account": account.name,
				"debit_in_account_currency": amount,
				"cost_center": get_default_cost_center(doc.company),
			},
		)
		je.insert()
		je.submit()
	finally:
		frappe.set_user(actor)
		frappe.local.session.clear()
		frappe.local.session.update(original_session)
		session_obj = getattr(frappe.local, "session_obj", None)
		if session_obj:
			session_obj.data = frappe.local.session
	doc.reload()
	if flt(doc.return_amount, 2) < previous_return + amount:
		frappe.throw(_("The advance return was not reflected in its ledger. No return was recorded."))
	return {
		"advance": doc.name,
		"journal_entry": je.name,
		"amount": amount,
		"returned_amount": flt(doc.return_amount, 2),
		"residual_amount": flt(advance_residual_amount(doc), 2),
	}
