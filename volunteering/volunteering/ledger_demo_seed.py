"""Opt-in, localhost-only ledger examples created through normal Home workflows.

Run with ``bench --site sevamrita.local execute
volunteering.volunteering.ledger_demo_seed.seed``. Never runs during migration.
Every source document is marked as fictional training data.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.utils import flt, nowdate

from volunteering.volunteering.demo_night_seed import _demo_receipt


SITE = "sevamrita.local"
PROJECT = "PROJ-0002"
PERSONAL_EMPLOYEE = "demo.tonight.employee@sevamrita.local"
ADVANCE_EMPLOYEE = "demo.tonight.advance.paid@sevamrita.local"
REVIEWER = "demo.tonight.receipts@sevamrita.local"
MANAGER = "demo.tonight.manager@sevamrita.local"
ACCOUNTS = "demo.tonight.accounts@sevamrita.local"
ADVANCE = "HR-EAD-2026-00006"
PERSONAL_MARKER = "Ledger training only: classroom learning materials; no real purchase or payment"
ADVANCE_MARKER = "Ledger training only: workbooks paid from a demo advance; no real purchase"


@contextmanager
def _as_user(user):
	previous = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(previous)


def _require_local_demo():
	if frappe.local.site != SITE:
		frappe.throw(f"Ledger training data may only be created on {SITE}.")
	if frappe.db.get_value("Project", PROJECT, "project_name") != "Training Demo — Balewadi Digital Learning Centre":
		frappe.throw("The known local training project is missing or was changed.")
	if frappe.db.get_value("Employee Advance", ADVANCE, "employee") != frappe.db.get_value(
		"Employee", {"user_id": ADVANCE_EMPLOYEE}, "name"
	):
		frappe.throw("The known paid training advance is missing or belongs to another employee.")
	if flt(frappe.db.get_value("Employee Advance", ADVANCE, "paid_amount")) < 1000:
		frappe.throw("The training advance has not been disbursed in full.")
	for account in ("Print and Stationery - SF", "Education Expenses - SF", "Cash - SF"):
		if not frappe.db.exists("Account", {"name": account, "company": "Sevamrita Foundation", "disabled": 0}):
			frappe.throw(f"Required training ledger is missing: {account}")


def _existing_claim(marker):
	return frappe.db.get_value("Expense Claim", {"remark": marker}, "name")


def _make_claim(user, marker, amount, sequence, *, advance=None):
	from volunteering.volunteering.expense_claim_portal import submit_expense_claim

	budget_key = frappe.db.get_value(
		"Project Account Budget", {"parent": PROJECT, "is_active": 1}, "budget_key", order_by="idx asc"
	)
	if not budget_key:
		frappe.throw("The training project needs one active expense break-up label.")
	payload = {
		"project": PROJECT,
		"reimbursement_source": "OWN_ADVANCE" if advance else "PERSONAL",
		"employee_advance": advance or "",
		"expenses": [
			{
				"expense_date": nowdate(),
				"account": budget_key,
				"supplier_name": "Demo Sunrise Learning Supplies",
				"invoice_number": f"LEDGER-DEMO-{sequence}",
				"description": marker,
				"amount": amount,
				"receipt_filename": f"ledger-training-{sequence}.pdf",
				"receipt_content": _demo_receipt(marker, amount, f"LEDGER-DEMO-{sequence}"),
			}
		],
	}
	with _as_user(user):
		return submit_expense_claim(payload)["name"]


def _approve_and_classify(name, amount, accounts):
	from volunteering.volunteering.expense_claim_workflow_portal import (
		classify_expense_claim_accounts,
		decide_expense_claim,
	)
	from volunteering.volunteering.receipt_review import review_receipts

	with _as_user(REVIEWER):
		review_receipts(name, "verify", "Fictional training receipt checked for ledger demonstration.")
	with _as_user(MANAGER):
		claim = frappe.get_doc("Expense Claim", name)
		decide_expense_claim(
			name, "approve", {row.name: flt(row.amount, 2) for row in claim.expenses},
			"Approved as local fictional ledger training data.",
		)
	with _as_user(ACCOUNTS):
		claim = frappe.get_doc("Expense Claim", name)
		if len(claim.expenses) != 1:
			frappe.throw("The training claim unexpectedly has multiple expense rows.")
		allocations = [{"expense_account": account, "amount": part} for account, part in accounts]
		if flt(sum(part for _, part in accounts), 2) != flt(amount, 2):
			frappe.throw("The training ledger split does not match the claim.")
		classify_expense_claim_accounts(
			name,
			[{"expense_detail": claim.expenses[0].name, "allocations": allocations}],
			"Fictional training allocation; not a Sevamrita purchase.",
		)


def seed():
	"""Post two idempotent demo claims: cash reimbursement and advance utilisation."""
	_require_local_demo()
	previous_user = frappe.session.user
	previous_mute = frappe.flags.mute_emails
	try:
		frappe.flags.mute_emails = True
		with (
			patch("frappe.sendmail"),
			patch("frappe.enqueue", lambda *args, **kwargs: None),
			patch(
				"frappe.workflow.doctype.workflow_action.workflow_action.send_workflow_action_email",
				lambda *args, **kwargs: None,
			),
		):
			personal = _existing_claim(PERSONAL_MARKER)
			if not personal:
				personal = _make_claim(PERSONAL_EMPLOYEE, PERSONAL_MARKER, 735, "PERSONAL")
				_approve_and_classify(
					personal, 735,
					[("Print and Stationery - SF", 500), ("Education Expenses - SF", 235)],
				)
				from volunteering.volunteering.expense_claim_workflow_portal import reimburse_expense_claim

				with _as_user(ACCOUNTS):
					reimburse_expense_claim(
						personal, {"paid_from": "Cash - SF", "posting_date": nowdate()}
					)

			advance_claim = _existing_claim(ADVANCE_MARKER)
			if not advance_claim:
				advance_claim = _make_claim(
					ADVANCE_EMPLOYEE, ADVANCE_MARKER, 420, "ADVANCE", advance=ADVANCE
				)
				_approve_and_classify(
					advance_claim, 420,
					[("Print and Stationery - SF", 420)],
				)
		frappe.db.commit()
		return verify()
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		frappe.set_user(previous_user)
		frappe.flags.mute_emails = previous_mute


def verify():
	"""Read back source documents and real, non-cancelled GL postings."""
	_require_local_demo()
	result = {}
	for key, marker in (("personal", PERSONAL_MARKER), ("advance", ADVANCE_MARKER)):
		name = _existing_claim(marker)
		if not name:
			result[key] = {"created": False}
			continue
		claim = frappe.get_doc("Expense Claim", name)
		ledger_rows = frappe.get_all(
			"GL Entry", filters={"voucher_type": "Expense Claim", "voucher_no": name, "is_cancelled": 0},
			fields=["account", "debit", "credit"], order_by="account asc", limit_page_length=20,
		)
		payments = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": "Expense Claim", "reference_name": name},
			fields=["parent"], limit_page_length=20,
		)
		result[key] = {
			"claim": name, "status": claim.status, "docstatus": claim.docstatus,
			"ledger": ledger_rows, "payment_entries": [row.parent for row in payments],
		}
	return {"site": frappe.local.site, "project": PROJECT, "examples": result}
