"""Final Expense Claim ledger classification performed by Accounts before posting."""

from __future__ import annotations

from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cstr, flt, now_datetime

PENDING_ACCOUNTS_CLASSIFICATION = "Pending Accounts Classification"
CLASSIFICATION_NOT_STARTED = "Not Started"
CLASSIFICATION_PENDING = "Pending"
CLASSIFICATION_COMPLETE = "Complete"


def can_classify(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return user == "Administrator" or "Accounts Manager" in frappe.get_roles(user)


def available_expense_accounts(company: str) -> list[dict]:
	return [
		{"value": row.name, "label": row.account_name or row.name, "description": row.name}
		for row in frappe.get_all(
			"Account",
			filters={"company": company, "root_type": "Expense", "is_group": 0, "disabled": 0},
			fields=["name", "account_name"],
			order_by="account_name asc",
			limit_page_length=0,
		)
	]


def _validate_account(account: str, company: str):
	from volunteering.volunteering.project_expense_accounts import _validate_account as validate

	return validate(account, company)


def prepare_account_classification(doc, method=None):
	"""Initialise the Accounts stage after final manager approval."""
	if doc.doctype != "Expense Claim":
		return
	previous = doc.get_doc_before_save()
	previous_state = previous.workflow_state if previous else None
	if doc.workflow_state == PENDING_ACCOUNTS_CLASSIFICATION and previous_state != doc.workflow_state:
		doc.account_classification_status = CLASSIFICATION_PENDING
		doc.account_classified_by = None
		doc.account_classified_on = None
		doc.account_classification_note = None
		doc.set("account_allocations", [])
	elif doc.workflow_state in ("Draft", "Pending Receipt Review", "Receipt Correction Required", "Pending Approval", "Rejected"):
		if previous_state != doc.workflow_state and doc.get("account_classification_status") != CLASSIFICATION_NOT_STARTED:
			doc.account_classification_status = CLASSIFICATION_NOT_STARTED
			doc.account_classified_by = None
			doc.account_classified_on = None
			doc.account_classification_note = None
			doc.set("account_allocations", [])


def _grouped_allocations(doc) -> dict[str, list]:
	grouped = defaultdict(list)
	for row in doc.get("account_allocations") or []:
		grouped[row.expense_detail].append(row)
	return grouped


def validate_account_allocations(doc, *, require_complete=True) -> dict[str, list]:
	"""Validate an exact, positive ledger split for every sanctioned expense row."""
	if require_complete and doc.get("account_classification_status") != CLASSIFICATION_COMPLETE:
		frappe.throw(_("Accounts must complete the expense-account classification before posting."))
	expenses = {row.name: row for row in doc.get("expenses") or []}
	grouped = _grouped_allocations(doc)
	unknown = set(grouped) - set(expenses)
	if unknown:
		frappe.throw(_("Account allocations contain an unknown expense item."))

	for detail, expense in expenses.items():
		required = flt(expense.sanctioned_amount, 2)
		rows = grouped.get(detail, [])
		if required <= 0:
			if any(flt(row.allocated_amount, 2) for row in rows):
				frappe.throw(_("A rejected expense item cannot have an account allocation."))
			continue
		if not rows:
			frappe.throw(_("Allocate the sanctioned amount for every expense item."))
		seen = set()
		total = 0.0
		for row in rows:
			account = cstr(row.expense_account).strip()
			amount = flt(row.allocated_amount, 2)
			if not account or amount <= 0:
				frappe.throw(_("Every account allocation must have an account and a positive amount."))
			if account in seen:
				frappe.throw(_("Use each ledger account only once per expense item."))
			seen.add(account)
			_validate_account(account, doc.company)
			total += amount
		if flt(total, 2) != required:
			frappe.throw(
				_("Allocated amount for {0} must equal {1}.").format(
					expense.description or detail, frappe.format_value(required, {"fieldtype": "Currency"})
				)
			)
	return grouped


def validate_account_classification_before_submit(doc, method=None):
	if doc.doctype == "Expense Claim":
		validate_account_allocations(doc)


def set_account_allocations(doc, rows, note=""):
	"""Replace the claim snapshot after validating an Accounts Manager payload."""
	if doc.docstatus != 0 or doc.workflow_state != PENDING_ACCOUNTS_CLASSIFICATION:
		frappe.throw(_("This claim is not awaiting Accounts classification."))
	if not can_classify():
		frappe.throw(_("Only an Accounts Manager can classify expense accounts."), frappe.PermissionError)
	if not isinstance(rows, list) or len(rows) > 250:
		frappe.throw(_("Invalid account-allocation data."))
	expenses = {row.name: row for row in doc.expenses}
	seen_details = set()
	doc.set("account_allocations", [])
	for item in rows:
		if not isinstance(item, dict) or set(item) != {"expense_detail", "allocations"}:
			frappe.throw(_("Invalid account-allocation row."))
		detail = cstr(item.get("expense_detail")).strip()
		allocations = item.get("allocations")
		if detail not in expenses or detail in seen_details or not isinstance(allocations, list):
			frappe.throw(_("Unknown or duplicate expense item in account allocations."))
		seen_details.add(detail)
		for allocation in allocations:
			if not isinstance(allocation, dict) or set(allocation) != {"expense_account", "amount"}:
				frappe.throw(_("Invalid ledger allocation."))
			doc.append(
				"account_allocations",
				{
					"expense_detail": detail,
					"expense_label": expenses[detail].get("project_expense_account") or expenses[detail].description,
					"expense_account": cstr(allocation.get("expense_account")).strip(),
					"allocated_amount": flt(allocation.get("amount"), 2),
				},
			)
	if seen_details != set(expenses):
		frappe.throw(_("Include every expense item in account allocations."))
	doc.account_classification_status = CLASSIFICATION_COMPLETE
	doc.account_classified_by = frappe.session.user
	doc.account_classified_on = now_datetime()
	doc.account_classification_note = cstr(note).strip()
	grouped = validate_account_allocations(doc)
	# Keep HRMS' hidden compatibility field aligned with the first final account.
	for detail, expense in expenses.items():
		if grouped.get(detail):
			expense.default_account = grouped[detail][0].expense_account
	return grouped


def classification_snapshot(doc, labels: dict[str, str]) -> dict:
	"""Portal-safe classification context (available only after access checks)."""
	from volunteering.volunteering.project_expense_accounts import suggested_accounts

	grouped = _grouped_allocations(doc)
	return {
		"status": doc.get("account_classification_status") or CLASSIFICATION_NOT_STARTED,
		"note": doc.get("account_classification_note") or "",
		"accounts": available_expense_accounts(doc.company),
		"items": [
			{
				"expense_detail": row.name,
				"label": labels.get(row.get("project_expense_account")) or row.description or _("Project expense"),
				"required_amount": flt(row.sanctioned_amount, 2),
				"suggested_accounts": suggested_accounts(doc.project, row.get("project_expense_account")),
				"allocations": [
					{"expense_account": item.expense_account, "amount": flt(item.allocated_amount, 2)}
					for item in grouped.get(row.name, [])
				],
			}
			for row in doc.expenses
		],
	}
