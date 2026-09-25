# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Permission-scoped Home UI services for the Expense Claim lifecycle.

This module intentionally delegates workflow decisions to the existing receipt
review, approval-routing, manager-float and Payment Entry services.  It exposes
only the claim currently actionable by the signed-in user and never makes
accounting fields editable by ordinary employees.
"""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import cint, cstr, flt, getdate, nowdate

from volunteering.volunteering.accounting_dashboard.constants import ACCOUNTS_ROLES
from volunteering.volunteering.approval_routing import (
	escalate_document,
	get_approver_action_flags,
)
from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details
from volunteering.volunteering.expense_claim_portal import _claim_source, _expense_labels, _project_names
from volunteering.volunteering.receipt_review import (
	PENDING_RECEIPT_REVIEW,
	RECEIPT_REVIEWER_ROLE,
	REVIEW_STATUS_VERIFIED,
	review_receipts,
)

HOME_ROUTE = "/volunteering/expense-claim-workflow"


def _roles(user: str | None = None) -> set[str]:
	return set(frappe.get_roles(user or frappe.session.user))


def _is_accounts_user(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or bool(_roles(user).intersection(ACCOUNTS_ROLES))


def _requester_user(doc) -> str | None:
	return frappe.db.get_value("Employee", doc.employee, "user_id") if doc.employee else doc.owner


def _can_receipt_review(doc, user: str) -> bool:
	return (
		(user == "Administrator" or RECEIPT_REVIEWER_ROLE in _roles(user))
		and doc.docstatus == 0
		and doc.workflow_state == PENDING_RECEIPT_REVIEW
		and _requester_user(doc) != user
	)


def _can_approve(doc, user: str) -> bool:
	return (
		doc.docstatus == 0
		and doc.workflow_state == "Pending Approval"
		and doc.get("pending_approver") == user
	)


def _can_reimburse(doc, user: str) -> bool:
	return (
		_is_accounts_user(user)
		and doc.docstatus == 1
		and doc.get("approval_status") == "Approved"
		and doc.get("status") == "Unpaid"
		and not cint(doc.get("is_paid"))
	)


def _assert_work_access(doc) -> dict:
	user = frappe.session.user
	access = {
		"receipt_review": _can_receipt_review(doc, user),
		"approval": _can_approve(doc, user),
		"reimbursement": _can_reimburse(doc, user),
	}
	if not any(access.values()):
		frappe.throw(_("This expense claim is not awaiting an action from you."), frappe.PermissionError)
	return access


def _queue_row(row, kind: str) -> dict:
	return {
		"name": row.name,
		"kind": kind,
		"employee_name": row.employee_name or row.employee or row.name,
		"project": row.project,
		"amount": flt(row.total_sanctioned_amount or row.total_claimed_amount, 2),
		"currency": row.currency or "INR",
		"posting_date": row.posting_date,
		"modified": row.modified,
		"route": f"{HOME_ROUTE}?claim={row.name}",
	}


@frappe.whitelist(methods=["POST"])
def get_expense_claim_work_queue():
	"""Return only the receipt, approval and payment work visible to this user."""
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to review expense claims."), frappe.PermissionError)

	fields = [
		"name",
		"employee",
		"employee_name",
		"project",
		"currency",
		"posting_date",
		"total_claimed_amount",
		"total_sanctioned_amount",
		"modified",
	]
	queues = {"receipt_review": [], "approval": [], "reimbursement": []}
	roles = _roles(user)
	if user == "Administrator" or RECEIPT_REVIEWER_ROLE in roles:
		filters = {"docstatus": 0, "workflow_state": PENDING_RECEIPT_REVIEW}
		employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if employee and user != "Administrator":
			filters["employee"] = ["!=", employee]
		queues["receipt_review"] = [
			_queue_row(row, "receipt_review")
			for row in frappe.get_all(
				"Expense Claim", filters=filters, fields=fields, order_by="modified desc", limit=200
			)
		]

	queues["approval"] = [
		_queue_row(row, "approval")
		for row in frappe.get_all(
			"Expense Claim",
			filters={
				"docstatus": 0,
				"workflow_state": "Pending Approval",
				"pending_approver": user,
			},
			fields=fields,
			order_by="modified desc",
			limit=200,
		)
	]

	if _is_accounts_user(user):
		queues["reimbursement"] = [
			_queue_row(row, "reimbursement")
			for row in frappe.get_all(
				"Expense Claim",
				filters={
					"docstatus": 1,
					"approval_status": "Approved",
					"status": "Unpaid",
				},
				fields=fields,
				order_by="posting_date asc, modified asc",
				limit=500,
			)
		]

	return {
		"can_review_receipts": user == "Administrator" or RECEIPT_REVIEWER_ROLE in roles,
		"can_reimburse": _is_accounts_user(user),
		"queues": queues,
		"counts": {key: len(value) for key, value in queues.items()},
	}


def _payment_options(doc) -> dict | None:
	if not _can_reimburse(doc, frappe.session.user):
		return None
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": doc.company,
			"is_group": 0,
			"disabled": 0,
			"account_type": ["in", ["Bank", "Cash"]],
		},
		fields=["name", "account_name", "account_type", "account_currency"],
		order_by="account_type asc, account_name asc",
		limit=500,
	)
	bank_details = get_approved_bank_details(doc.employee, reveal=False)
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
		"approved_bank": bank_details,
		"posting_date": nowdate(),
	}


@frappe.whitelist(methods=["POST"])
def get_expense_claim_work_item(name: str):
	doc = frappe.get_doc("Expense Claim", cstr(name).strip())
	access = _assert_work_access(doc)
	projects = _project_names([doc.project])
	labels = _expense_labels(doc.project)
	flags = (
		get_approver_action_flags("Expense Claim", doc.name)
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
		"project": doc.project,
		"project_name": projects.get(doc.project) or doc.project,
		"posting_date": doc.posting_date,
		"currency": doc.currency or "INR",
		"source": _claim_source(doc),
		"workflow_state": doc.workflow_state,
		"approval_status": doc.approval_status,
		"receipt_review_status": doc.get("receipt_review_status") or "Not Submitted",
		"receipt_review_notes": doc.get("receipt_review_notes") or "",
		"remark": doc.remark or "",
		"claimed_amount": flt(doc.total_claimed_amount, 2),
		"sanctioned_amount": flt(doc.total_sanctioned_amount, 2),
		"reimbursed_amount": flt(doc.total_amount_reimbursed, 2),
		"access": access,
		"approval_flags": flags,
		"payment": _payment_options(doc),
		"expenses": [
			{
				"name": row.name,
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
	}


@frappe.whitelist(methods=["POST"])
def review_expense_claim_receipts(name: str, decision: str, notes: str = "", checklist=None):
	"""Home wrapper around the canonical receipt-review service."""
	doc = frappe.get_doc("Expense Claim", cstr(name).strip())
	if not _can_receipt_review(doc, frappe.session.user):
		frappe.throw(_("This expense claim is not awaiting your receipt review."), frappe.PermissionError)
	review_receipts(doc.name, decision, notes)
	return {"name": doc.name, "decision": decision}


def _parse_sanctioned_amounts(value) -> dict[str, float]:
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except TypeError, ValueError:
			frappe.throw(_("The sanctioned amounts are invalid."))
	if not isinstance(value, dict):
		frappe.throw(_("Enter a sanctioned amount for every expense item."))
	return {cstr(key): flt(amount, 2) for key, amount in value.items()}


@frappe.whitelist(methods=["POST"])
def decide_expense_claim(name: str, action: str, sanctioned_amounts=None, reason: str = ""):
	"""Approve, reject or escalate the claim through its configured workflow."""
	doc = frappe.get_doc("Expense Claim", cstr(name).strip())
	if not _can_approve(doc, frappe.session.user):
		frappe.throw(_("Only the current pending approver can decide this claim."), frappe.PermissionError)
	action = cstr(action).strip().lower()
	reason = cstr(reason).strip()
	flags = get_approver_action_flags("Expense Claim", doc.name)

	if action == "escalate":
		if not flags.get("can_escalate"):
			frappe.throw(_("This claim can be decided at your approval level and cannot be escalated."))
		if not reason:
			frappe.throw(_("Give a reason for escalation."))
		escalate_document("Expense Claim", doc.name, reason)
		return {"name": doc.name, "action": "escalated"}

	if action == "reject":
		if not flags.get("can_reject"):
			frappe.throw(_("You cannot reject this claim."), frappe.PermissionError)
		if not reason:
			frappe.throw(_("Give a reason for rejection."))
		doc.add_comment("Comment", _("Claim rejected: {0}").format(reason))
		apply_workflow(doc, "Reject")
		return {"name": doc.name, "action": "rejected"}

	if action != "approve":
		frappe.throw(_("Choose Approve, Reject or Escalate."))
	if not flags.get("can_approve"):
		messages = flags.get("strict_budget_messages") or []
		frappe.throw(
			cstr(
				flags.get("manager_float_message")
				or "\n".join(messages)
				or _("This claim requires escalation.")
			)
		)

	amounts = _parse_sanctioned_amounts(sanctioned_amounts)
	expected = {row.name for row in doc.expenses}
	if set(amounts) != expected:
		frappe.throw(_("Enter a sanctioned amount for every expense item."))
	total = 0.0
	for row in doc.expenses:
		amount = amounts[row.name]
		if amount < 0 or amount > flt(row.amount, 2):
			frappe.throw(
				_("Sanctioned amount for {0} must be between zero and the claimed amount.").format(
					row.description or row.name
				)
			)
		row.sanctioned_amount = amount
		total += amount
	if flt(total, 2) <= 0:
		frappe.throw(_("Approve at least one expense amount, or reject the claim."))
	doc.save()
	if reason:
		doc.add_comment("Comment", _("Approval note: {0}").format(reason))
	apply_workflow(doc, "Approve")
	return {"name": doc.name, "action": "approved", "sanctioned_amount": flt(total, 2)}


def _validate_payment_account(company: str, account: str):
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
		or cint(row.is_group)
		or cint(row.disabled)
	):
		frappe.throw(_("Select an enabled Bank or Cash account belonging to this company."))
	return row


@frappe.whitelist(methods=["POST"])
def reimburse_expense_claim(name: str, payment=None):
	"""Create and submit one real Payment Entry for an approved outstanding claim."""
	if not _is_accounts_user():
		frappe.throw(_("Accounts access is required to reimburse a claim."), frappe.PermissionError)
	data = frappe.parse_json(payment) if isinstance(payment, str) else payment
	if not isinstance(data, dict):
		frappe.throw(_("Payment details are required."))
	allowed = {"paid_from", "mode_of_payment", "posting_date", "reference_no", "reference_date"}
	if set(data) - allowed:
		frappe.throw(_("The payment contains unsupported fields."))

	claim_name = cstr(name).strip()
	frappe.db.sql("SELECT name FROM `tabExpense Claim` WHERE name=%s FOR UPDATE", claim_name)
	doc = frappe.get_doc("Expense Claim", claim_name)
	if not _can_reimburse(doc, frappe.session.user):
		frappe.throw(_("This claim is not approved and awaiting reimbursement."))
	if doc.get("receipt_review_status") != REVIEW_STATUS_VERIFIED:
		frappe.throw(_("Receipt review must be Verified before reimbursement."))

	from hrms.hr.doctype.expense_claim.expense_claim import get_outstanding_amount_for_claim
	from hrms.overrides.employee_payment_entry import get_payment_entry_for_employee

	outstanding = flt(get_outstanding_amount_for_claim(doc.name), 2)
	if outstanding <= 0:
		frappe.throw(_("This expense claim has no outstanding reimbursement."))
	account = _validate_payment_account(doc.company, data.get("paid_from"))
	posting_date = getdate(data.get("posting_date") or nowdate())
	if posting_date > getdate(nowdate()):
		frappe.throw(_("Payment posting date cannot be in the future."))

	pe = get_payment_entry_for_employee("Expense Claim", doc.name, bank_account=account.name)
	pe.posting_date = posting_date
	mode = cstr(data.get("mode_of_payment")).strip()
	if mode:
		if not frappe.db.exists("Mode of Payment", {"name": mode, "enabled": 1}):
			frappe.throw(_("Choose an enabled Mode of Payment."))
		pe.mode_of_payment = mode

	if account.account_type == "Bank":
		approved = get_approved_bank_details(doc.employee, reveal=False)
		if not approved:
			frappe.throw(
				_("An Accounts Manager must approve this employee's bank details before bank reimbursement.")
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
	doc.reload()
	return {
		"claim": doc.name,
		"payment_entry": pe.name,
		"amount": outstanding,
		"status": doc.status,
		"paid_from": pe.paid_from,
	}
