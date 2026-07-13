"""Idempotent Payment Entry creation for successful donations."""

from __future__ import annotations

import frappe
from frappe.utils import flt, nowdate

from volunteering.volunteering.api.volunteer_donor import ensure_customer_for_volunteer
from volunteering.volunteering.doctype.cashfree_settings.cashfree_settings import (
	get_cashfree_settings,
)


def create_payment_entry_for_donation(donation_name: str) -> str | None:
	"""Create and submit a Receive Payment Entry once. Returns PE name or None if skipped."""
	donation = frappe.get_doc("Donation", donation_name)

	if donation.payment_entry:
		return donation.payment_entry

	if donation.status != "Success":
		return None

	settings = get_cashfree_settings()
	if not settings.create_payment_entry:
		return None

	if not settings.company or not settings.mode_of_payment or not settings.paid_to_account:
		frappe.log_error(
			title="Donation Payment Entry skipped",
			message=(
				f"Donation {donation_name}: Cashfree Settings missing company / "
				"mode of payment / paid_to_account"
			),
		)
		return None

	customer = donation.customer
	if not customer and donation.volunteer:
		customer = ensure_customer_for_volunteer(
			donation.volunteer, donation.full_name, donation.email
		)
		donation.db_set("customer", customer, update_modified=False)

	if not customer:
		frappe.log_error(
			title="Donation Payment Entry skipped",
			message=f"Donation {donation_name}: no Customer available",
		)
		return None

	paid_amount = flt(donation.amount)
	paid_from = _party_receivable_account(customer, settings.company)
	if not paid_from:
		frappe.log_error(
			title="Donation Payment Entry skipped",
			message=f"Donation {donation_name}: no receivable account for Customer {customer}",
		)
		return None

	pe = frappe.new_doc("Payment Entry")
	pe.payment_type = "Receive"
	pe.company = settings.company
	pe.posting_date = nowdate()
	pe.mode_of_payment = settings.mode_of_payment
	pe.party_type = "Customer"
	pe.party = customer
	pe.paid_from = paid_from
	pe.paid_to = settings.paid_to_account
	pe.paid_amount = paid_amount
	pe.received_amount = paid_amount
	pe.target_exchange_rate = 1
	pe.source_exchange_rate = 1
	pe.paid_from_account_currency = (
		frappe.get_cached_value("Account", paid_from, "account_currency") or "INR"
	)
	pe.paid_to_account_currency = (
		frappe.get_cached_value("Account", settings.paid_to_account, "account_currency") or "INR"
	)

	if hasattr(pe, "set_missing_values"):
		pe.set_missing_values()
	if hasattr(pe, "set_exchange_rate"):
		pe.set_exchange_rate()
	if hasattr(pe, "set_amounts"):
		pe.set_amounts()

	pe.reference_no = donation.cf_payment_id or donation.cashfree_order_id or donation.name
	pe.reference_date = nowdate()
	pe.remarks = f"Donation {donation.name} via Cashfree (Volunteer {donation.volunteer or ''})"

	pe.insert(ignore_permissions=True)
	pe.submit()

	donation.db_set("payment_entry", pe.name, update_modified=False)
	return pe.name


def _party_receivable_account(customer: str, company: str) -> str | None:
	try:
		from erpnext.accounts.party import get_party_account

		return get_party_account("Customer", customer, company)
	except Exception:
		return frappe.get_cached_value("Company", company, "default_receivable_account")
