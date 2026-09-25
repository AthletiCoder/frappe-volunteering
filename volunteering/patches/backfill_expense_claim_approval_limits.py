import frappe


def execute():
	"""Give existing grades the same Expense Claim authority they already use elsewhere."""
	if not frappe.db.has_column("Designation Approval Limit", "max_expense_claim_amount"):
		return

	frappe.db.sql(
		"""
		UPDATE `tabDesignation Approval Limit`
		SET max_expense_claim_amount = max_approve_amount
		WHERE COALESCE(max_expense_claim_amount, 0) = 0
		  AND COALESCE(max_approve_amount, 0) > 0
		"""
	)
	frappe.clear_cache(doctype="Approval and Advance Limits")
