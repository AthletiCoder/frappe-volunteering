import frappe

from volunteering.volunteering.accounting_setup import (
	backfill_project_expense_accounts,
	has_current_site_column,
	setup_accounting_custom_fields,
)


def execute():
	# This one-time backfill runs before after_migrate. A pre-existing Custom
	# Field record does not guarantee that its database column was synced.
	setup_accounting_custom_fields()
	for doctype, fieldname in (
		("Project Account Budget", "employee_label"),
		("Expense Claim Detail", "project_expense_account"),
	):
		if not has_current_site_column(doctype, fieldname):
			frappe.db.updatedb(doctype)
		if not has_current_site_column(doctype, fieldname):
			raise RuntimeError(f"Cannot backfill {doctype}: missing {fieldname} column")
	backfill_project_expense_accounts(seed_empty_projects=True)
