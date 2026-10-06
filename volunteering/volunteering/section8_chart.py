"""Reviewable, additive Section 8 chart template.

This is intentionally NOT an after-migrate hook. A production chart may be
empty of GL entries but still referenced by company defaults and workflows.
Review the preview with Sevamrita's CA, back up the site, then invoke apply
explicitly. Existing accounts are never renamed, moved, disabled or deleted.
"""

from __future__ import annotations

import frappe
from frappe import _

from volunteering.volunteering.chart_of_accounts_portal import SEVAMRITA_COMPANY

# (root type, parent label, label, is group, ERPNext account type)
NODES = (
	("Asset", None, "Bank Accounts", 1, ""),
	# A generic domestic-bank heading is a group; actual bank ledgers stay distinct.
	("Asset", "Bank Accounts", "Domestic Bank Account", 1, ""),
	("Asset", "Bank Accounts", "FCRA Bank / Utilisation Accounts", 1, ""),
	# The existing ERPNext chart already has this as a group with a Cash ledger below it.
	("Asset", None, "Cash in Hand", 1, ""),
	("Asset", None, "Donations / Grants Receivable", 0, ""),
	("Asset", None, "Employee Advances", 0, ""),
	("Asset", None, "Vendor Advances", 0, ""),
	("Asset", None, "Prepaid Expenses", 0, ""),
	("Asset", None, "Security Deposits", 0, ""),
	("Asset", None, "Fixed Assets", 1, ""),
	("Asset", "Fixed Assets", "Furniture and Fixtures", 0, "Fixed Asset"),
	("Asset", "Fixed Assets", "Computers and IT Equipment", 0, "Fixed Asset"),
	("Asset", "Fixed Assets", "Kitchen Equipment", 0, "Fixed Asset"),
	("Asset", "Fixed Assets", "Accumulated Depreciation", 0, ""),
	("Liability", None, "Employee Reimbursements Payable", 0, "Payable"),
	("Liability", None, "Supplier Payables", 0, "Payable"),
	("Liability", None, "Accrued Expenses", 0, ""),
	("Liability", None, "Statutory Dues", 1, ""),
	("Liability", "Statutory Dues", "TDS Payable", 0, "Tax"),
	# Combined wording is only a heading; input credits and amounts payable must
	# be split into appropriate asset/liability posting accounts after CA review.
	("Liability", "Statutory Dues", "GST Payable / Input GST", 1, ""),
	("Liability", "Statutory Dues", "PF Payable", 0, ""),
	("Liability", "Statutory Dues", "ESI Payable", 0, ""),
	("Liability", None, "Grants Received in Advance", 0, ""),
	# This site's existing chart has a combined Liabilities/Funds root, like the PDF.
	# Final balance-sheet classification still needs the CA's approval.
	("Liability", None, "Funds and Reserves", 1, ""),
	("Liability", "Funds and Reserves", "General Fund", 0, ""),
	("Liability", "Funds and Reserves", "Corpus Fund", 0, ""),
	("Liability", "Funds and Reserves", "Restricted Funds", 0, ""),
	("Liability", "Funds and Reserves", "Surplus / Deficit", 0, ""),
	("Income", None, "General Donations", 0, ""),
	("Income", None, "Corpus Donations", 0, ""),
	("Income", None, "Restricted Donations / Grants", 0, ""),
	("Income", None, "CSR Grants", 0, ""),
	("Income", None, "Membership Fees", 0, ""),
	("Income", None, "Programme Income", 0, ""),
	("Income", None, "Interest Income", 0, ""),
	("Income", None, "Other Income", 0, ""),
	("Expense", None, "Programme Expenses", 1, ""),
	("Expense", "Programme Expenses", "Beneficiary Supplies", 0, ""),
	("Expense", "Programme Expenses", "Food and Groceries", 0, ""),
	("Expense", "Programme Expenses", "Medical Expenses", 0, ""),
	("Expense", "Programme Expenses", "Education Expenses", 0, ""),
	("Expense", "Programme Expenses", "Event Expenses", 0, ""),
	("Expense", None, "Employee Costs", 0, ""),
	("Expense", None, "Travel and Conveyance", 0, ""),
	("Expense", None, "Rent and Utilities", 0, ""),
	("Expense", None, "Printing and Stationery", 0, ""),
	("Expense", None, "Kitchen Utensils and Small Equipment", 0, ""),
	("Expense", None, "Professional, Legal and Audit Fees", 0, ""),
	("Expense", None, "IT and Communication", 0, ""),
	("Expense", None, "Fundraising and Publicity", 0, ""),
	("Expense", None, "Bank and Payment Gateway Charges", 0, ""),
	("Expense", None, "Depreciation", 0, ""),
)


def _root(company, root_type):
	return frappe.db.get_value(
		"Account", {"company": company, "root_type": root_type, "parent_account": ["is", "not set"]}, "name"
	)


def preview_section8_chart(company=SEVAMRITA_COMPANY, include_fcra=False):
	"""Classify every proposed node before changing anything."""
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company does not exist."))
	roots = {kind: _root(company, kind) for kind in ("Asset", "Liability", "Income", "Expense")}
	missing_roots = [kind for kind, name in roots.items() if not name]
	if missing_roots:
		frappe.throw(_("Missing root accounts: {0}").format(", ".join(missing_roots)))
	result = []
	for root_type, parent_label, label, is_group, account_type in NODES:
		if label == "FCRA Bank / Utilisation Accounts" and not include_fcra:
			continue
		rows = frappe.get_all(
			"Account", filters={"company": company, "account_name": label},
			fields=["name", "parent_account", "is_group", "root_type", "account_type", "disabled"],
			limit_page_length=0,
		)
		status = "create"
		if rows:
			status = "existing" if len(rows) == 1 and rows[0].root_type == root_type and int(rows[0].is_group) == is_group else "conflict"
		result.append({"root_type": root_type, "parent_label": parent_label or "", "label": label, "is_group": is_group, "account_type": account_type, "status": status, "matches": [row.name for row in rows]})
	return {"company": company, "roots": roots, "nodes": result, "has_conflicts": any(row["status"] == "conflict" for row in result), "note": "No account is renamed, moved, disabled or deleted. Review classification with a CA before applying. FCRA heading is optional."}


def apply_section8_chart(company=SEVAMRITA_COMPANY, *, confirmed=False, include_fcra=False):
	"""Create missing nodes only. Must be called explicitly after CA approval."""
	if not confirmed:
		frappe.throw(_("Pass confirmed=True only after CA review, a database backup, and a clean preview."))
	preview = preview_section8_chart(company, include_fcra=include_fcra)
	if preview["has_conflicts"]:
		frappe.throw(_("The proposed chart conflicts with existing names or account types. Resolve manually first."))
	created = []
	for row in preview["nodes"]:
		if row["status"] == "existing":
			continue
		parent = preview["roots"][row["root_type"]]
		if row["parent_label"]:
			parent = frappe.db.get_value("Account", {"company": company, "account_name": row["parent_label"], "is_group": 1}, "name")
		if not parent:
			frappe.throw(_("Missing group for {0}.").format(row["label"]))
		doc = frappe.get_doc({"doctype": "Account", "company": company, "account_name": row["label"], "parent_account": parent, "is_group": row["is_group"], "account_type": row["account_type"], "root_type": row["root_type"], "report_type": "Profit and Loss" if row["root_type"] in ("Income", "Expense") else "Balance Sheet"})
		doc.insert(ignore_permissions=True)
		created.append(doc.name)
	return {"created": created, "preview": preview_section8_chart(company, include_fcra=include_fcra)}
