# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""
Payout provider stub for future Cashfree Payouts.

Phase 1: all outbound disbursements use manual Payment Entry.
Phase 2: implement CashfreePayoutProvider.create_payout without changing PE GL posting.
"""

from __future__ import annotations

import frappe
from frappe import _

from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)


class PayoutProvider:
	"""Interface for outbound payout initiation."""

	def create_payout(self, payment_entry):
		raise NotImplementedError

	def get_status(self, payout_ref):
		raise NotImplementedError


class ManualPayoutProvider(PayoutProvider):
	def create_payout(self, payment_entry):
		return {
			"provider": "manual",
			"status": "manual",
			"message": _("Create and submit Payment Entry in ERPNext (bank/NEFT/UPI)."),
			"payment_entry": payment_entry,
		}

	def get_status(self, payout_ref):
		return {"provider": "manual", "status": "manual", "ref": payout_ref}


class CashfreePayoutProvider(PayoutProvider):
	"""Placeholder — not implemented in Phase 1."""

	def create_payout(self, payment_entry):
		frappe.throw(
			_(
				"Cashfree Payouts are not enabled yet. "
				"Use Manual Payment Entry, or set Preferred Payout Mode to Manual."
			),
			title=_("Payout Provider Not Ready"),
		)

	def get_status(self, payout_ref):
		frappe.throw(_("Cashfree Payout status is not available yet."))


def get_payout_provider():
	settings = get_accounting_settings()
	name = (settings.get("payout_provider") or "manual").lower()
	if name == "cashfree":
		return CashfreePayoutProvider()
	return ManualPayoutProvider()


@frappe.whitelist()
def initiate_payout(payment_entry):
	"""Whitelisted entry for future UI buttons. Phase 1 returns manual guidance."""
	frappe.has_permission("Payment Entry", "write", throw=True)
	return get_payout_provider().create_payout(payment_entry)
