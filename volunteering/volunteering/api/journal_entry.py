"""Income-recognition Journal Entry for successful donations."""

from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from volunteering.volunteering.api.payment_entry import _party_receivable_account
from volunteering.volunteering.doctype.cashfree_settings.cashfree_settings import (
	get_cashfree_settings,
)


def create_income_journal_entry_for_donation(donation_name: str) -> str | None:
	"""Post Dr Debtors / Cr Donation Income once, after the receipt Payment Entry."""
	donation = frappe.get_doc("Donation", donation_name)

	if donation.journal_entry:
		return donation.journal_entry

	if donation.status != "Success" or not donation.payment_entry:
		return None

	settings = get_cashfree_settings()
	if not settings.create_payment_entry or not settings.income_account:
		return None

	if not settings.company:
		return None

	customer = donation.customer
	if not customer:
		frappe.log_error(
			title="Donation income JE skipped",
			message=f"Donation {donation_name}: no Customer on donation",
		)
		return None

	receivable = _party_receivable_account(customer, settings.company)
	if not receivable:
		frappe.log_error(
			title="Donation income JE skipped",
			message=f"Donation {donation_name}: no receivable account for Customer {customer}",
		)
		return None

	amount = flt(donation.amount)
	if amount <= 0:
		return None

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = settings.company
	je.posting_date = nowdate()
	je.user_remark = f"Donation income — {donation.name}"
	je.cheque_no = donation.cf_payment_id or donation.cashfree_order_id or donation.name
	je.cheque_date = nowdate()

	je.append(
		"accounts",
		{
			"account": receivable,
			"party_type": "Customer",
			"party": customer,
			"debit_in_account_currency": amount,
		},
	)
	je.append(
		"accounts",
		{
			"account": settings.income_account,
			"credit_in_account_currency": amount,
		},
	)

	je.insert(ignore_permissions=True)
	je.submit()

	donation.db_set("journal_entry", je.name, update_modified=False)
	return je.name
