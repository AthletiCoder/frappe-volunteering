"""One-time, guarded reorganisation of the production Sevamrita account tree.

The chart change is kept in a patch rather than an ``after_migrate`` hook so
Frappe records its execution once. Other sites remain untouched.
"""

import frappe

from volunteering.volunteering.sevamrita_chart_reorganization import (
	apply_sevamrita_chart,
	preview_sevamrita_chart,
)


PRODUCTION_SITE = "sevamrita.m.frappe.cloud"
COMPANY = "Sevamrita Foundation"


def execute():
	if frappe.local.site != PRODUCTION_SITE:
		return
	apply_reviewed_chart()


def apply_reviewed_chart():
	"""Apply only to the reviewed, unposted chart; abort transaction on drift."""
	preview = preview_sevamrita_chart(COMPANY)
	if preview["conflicts"]:
		frappe.throw("Sevamrita chart migration conflicts: " + "; ".join(preview["conflicts"]))
	if preview["posted_gl_entries"]:
		frappe.throw("Sevamrita chart migration stopped: posted GL entries now exist")

	previous_user = frappe.session.user
	try:
		frappe.set_user("Administrator")
		apply_sevamrita_chart(COMPANY, confirmed=True)
		verify_bank_tree()
	finally:
		frappe.set_user(previous_user or "Guest")


def verify_bank_tree():
	"""Fail the patch if the requested bank hierarchy was not produced."""
	accounts = {
		row.account_name: row
		for row in frappe.get_all(
			"Account",
			filters={
				"company": COMPANY,
				"account_name": ["in", [
					"Bank Accounts", "Domestic Bank Accounts", "FCRA Accounts",
					"SF Axis Bank", "Cashfree Clearing",
				]],
			},
			fields=["name", "account_name", "parent_account", "is_group", "account_type"],
		)
	}
	if set(accounts) != {
		"Bank Accounts", "Domestic Bank Accounts", "FCRA Accounts",
		"SF Axis Bank", "Cashfree Clearing",
	}:
		frappe.throw("Sevamrita chart migration did not create the complete bank tree")
	bank, domestic, fcra = (
		accounts["Bank Accounts"], accounts["Domestic Bank Accounts"], accounts["FCRA Accounts"]
	)
	if not bank.is_group or not domestic.is_group or not fcra.is_group:
		frappe.throw("Sevamrita chart migration bank groups are not groups")
	if domestic.parent_account != bank.name or fcra.parent_account != bank.name:
		frappe.throw("Sevamrita chart migration bank groups have the wrong parent")
	for label in ("SF Axis Bank", "Cashfree Clearing"):
		account = accounts[label]
		if account.is_group or account.account_type != "Bank" or account.parent_account != domestic.name:
			frappe.throw(f"Sevamrita chart migration placed {label} incorrectly")
	if frappe.db.count("Account", {"parent_account": fcra.name}):
		frappe.throw("Sevamrita chart migration unexpectedly populated FCRA Accounts")
