"""Home UI service for Expense Claim approval limits."""

from __future__ import annotations

import json

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.authority import BOARD_OF_DIRECTORS

MANAGER_ROLE = "Accounts Manager"


def _require_accounts_manager():
	user = frappe.session.user
	if user == "Administrator" or MANAGER_ROLE in frappe.get_roles(user):
		return
	frappe.throw(
		_("Only Accounts Managers and Administrator may configure Expense Claim approval limits."),
		frappe.PermissionError,
	)


def _payload():
	doc = frappe.get_single("Approval and Advance Limits")
	return {
		"can_edit": True,
		"currency": frappe.defaults.get_global_default("currency") or "INR",
		"rows": [
			{
				"grade": row.designation,
				"expense_claim_limit": flt(row.max_expense_claim_amount, 2),
				"advance_approval_limit": flt(row.max_approve_amount, 2),
				"unlimited": row.designation == BOARD_OF_DIRECTORS,
			}
			for row in doc.get("designation_limits") or []
			if row.designation
		],
	}


@frappe.whitelist()
def get_expense_approval_limits():
	_require_accounts_manager()
	return _payload()


@frappe.whitelist(methods=["POST"])
def save_expense_approval_limits(rows):
	_require_accounts_manager()
	if isinstance(rows, str):
		try:
			rows = json.loads(rows)
		except TypeError, ValueError:
			frappe.throw(_("The Expense Claim limits are invalid."))
	if not isinstance(rows, list):
		frappe.throw(_("The Expense Claim limits are invalid."))

	doc = frappe.get_single("Approval and Advance Limits")
	by_grade = {row.designation: row for row in doc.get("designation_limits") or []}
	seen = set()
	for item in rows:
		if not isinstance(item, dict):
			frappe.throw(_("Every Expense Claim limit must identify a grade and amount."))
		grade = str(item.get("grade") or "").strip()
		if not grade or grade in seen or grade not in by_grade:
			frappe.throw(_("Choose each configured Employee Grade exactly once."))
		seen.add(grade)
		amount = flt(item.get("expense_claim_limit"), 2)
		if amount < 0:
			frappe.throw(_("The Expense Claim limit for {0} cannot be negative.").format(grade))
		by_grade[grade].max_expense_claim_amount = 0 if grade == BOARD_OF_DIRECTORS else amount

	if seen != set(by_grade):
		frappe.throw(_("Submit a limit for every configured Employee Grade."))

	doc.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Approval and Advance Limits")
	return _payload()
