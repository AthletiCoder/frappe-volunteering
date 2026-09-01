"""Donation ledgers, Cashfree mode of payment, and Cashfree Settings defaults."""

from __future__ import annotations

import frappe

CASHFREE_CLEARING_NAME = "Cashfree Clearing"
DONATION_INCOME_NAME = "Donation Income"
CASHFREE_MODE_OF_PAYMENT = "Cashfree"


def ensure_donation_accounting():
	"""Seed donation ledgers and wire Cashfree Settings when a Company exists."""
	if not frappe.db.exists("DocType", "Account"):
		return

	for company in frappe.get_all("Company", pluck="name"):
		clearing = _ensure_cashfree_clearing_account(company)
		income = _ensure_donation_income_account(company)
		if clearing:
			_ensure_cashfree_mode_of_payment(company, clearing)
		_ensure_cashfree_settings_defaults(company, clearing, income)


def _ensure_cashfree_clearing_account(company: str) -> str | None:
	existing = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": CASHFREE_CLEARING_NAME, "is_group": 0},
		"name",
	)
	if existing:
		return existing

	parent = _bank_group_parent(company)
	if not parent:
		frappe.log_error(
			title="Cashfree Clearing account skipped",
			message=f"No Bank group parent for company {company}",
		)
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": CASHFREE_CLEARING_NAME,
			"company": company,
			"parent_account": parent,
			"is_group": 0,
			"root_type": "Asset",
			"report_type": "Balance Sheet",
			"account_type": "Bank",
			"account_currency": frappe.db.get_value("Company", company, "default_currency"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _ensure_donation_income_account(company: str) -> str | None:
	existing = frappe.db.get_value(
		"Account",
		{"company": company, "account_name": DONATION_INCOME_NAME, "is_group": 0},
		"name",
	)
	if existing:
		return existing

	parent = frappe.db.get_value(
		"Account",
		{"company": company, "is_group": 1, "root_type": "Income"},
		"name",
		order_by="lft asc",
	)
	if not parent:
		frappe.log_error(
			title="Donation Income account skipped",
			message=f"No Income parent for company {company}",
		)
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": DONATION_INCOME_NAME,
			"company": company,
			"parent_account": parent,
			"is_group": 0,
			"root_type": "Income",
			"report_type": "Profit and Loss",
			"account_currency": frappe.db.get_value("Company", company, "default_currency"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _bank_group_parent(company: str) -> str | None:
	parent = frappe.db.get_value(
		"Account",
		{"company": company, "is_group": 1, "account_type": "Bank"},
		"name",
		order_by="lft asc",
	)
	if parent:
		return parent
	return frappe.db.get_value(
		"Account",
		{"company": company, "is_group": 1, "root_type": "Asset"},
		"name",
		order_by="lft asc",
	)


def _ensure_cashfree_mode_of_payment(company: str, clearing_account: str) -> str | None:
	if not frappe.db.exists("DocType", "Mode of Payment"):
		return None

	if frappe.db.exists("Mode of Payment", CASHFREE_MODE_OF_PAYMENT):
		mop_name = CASHFREE_MODE_OF_PAYMENT
	else:
		mop = frappe.get_doc(
			{
				"doctype": "Mode of Payment",
				"mode_of_payment": CASHFREE_MODE_OF_PAYMENT,
				"type": "Bank",
			}
		)
		mop.insert(ignore_permissions=True)
		mop_name = mop.name

	if not frappe.db.exists(
		"Mode of Payment Account",
		{"parent": mop_name, "company": company},
	):
		mop_doc = frappe.get_doc("Mode of Payment", mop_name)
		mop_doc.append("accounts", {"company": company, "default_account": clearing_account})
		mop_doc.save(ignore_permissions=True)

	return mop_name


def _ensure_cashfree_settings_defaults(
	company: str,
	clearing_account: str | None,
	income_account: str | None,
):
	if not frappe.db.exists("DocType", "Cashfree Settings"):
		return

	settings = frappe.get_single("Cashfree Settings")
	changed = False

	if not settings.company:
		settings.company = company
		changed = True
	if clearing_account and not settings.paid_to_account:
		settings.paid_to_account = clearing_account
		changed = True
	if income_account and not settings.income_account:
		settings.income_account = income_account
		changed = True
	if not settings.mode_of_payment and frappe.db.exists("Mode of Payment", CASHFREE_MODE_OF_PAYMENT):
		settings.mode_of_payment = CASHFREE_MODE_OF_PAYMENT
		changed = True

	if changed:
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
