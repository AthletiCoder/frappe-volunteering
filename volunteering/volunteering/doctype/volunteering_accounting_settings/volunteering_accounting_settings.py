# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


DEFAULT_DESIGNATION_LIMITS = (
	("Associate", 0, 2000),
	("Manager", 2000, 5000),
	("Vice President", 5000, 10000),
	("President", 10000, 15000),
	("Director", 25000, 25000),
	("CEO", 50000, 50000),
	("Executive Board", 100000, 100000),
	("Board of Directors", 0, 0),  # 0 approve = unlimited when flagged below
)

UNLIMITED_DESIGNATIONS = {"Board of Directors"}


class VolunteeringAccountingSettings(Document):
	pass


def get_accounting_settings():
	"""Return accounting settings with defaults if not yet created."""
	if frappe.db.exists("DocType", "Volunteering Accounting Settings"):
		return frappe.get_cached_doc("Volunteering Accounting Settings")
	return frappe._dict(
		tier_1_limit=2000,
		tier_2_limit=10000,
		use_designation_approval=1,
		vendor_payment_threshold=5000,
		cash_payment_limit=2000,
		invoice_split_window_days=7,
		max_unsettled_advances=1,
		advance_replenish_residual_pct=10,
		enable_budget_warnings=1,
		budget_hard_block_pct=25,
		budget_override_role="NGO Board Chairperson",
		emergency_submit_working_days=1,
		emergency_approve_working_days=2,
		preferred_payout_mode="Manual",
		payout_provider="manual",
	)


def get_designation_limit_map(settings=None):
	"""Return {designation_name: {max_approve_amount, max_advance_amount, unlimited}}."""
	settings = settings or get_accounting_settings()
	limits = {}
	for row in settings.get("designation_limits") or []:
		if not row.designation:
			continue
		unlimited = row.designation in UNLIMITED_DESIGNATIONS
		limits[row.designation] = {
			"max_approve_amount": flt(row.max_approve_amount),
			"max_advance_amount": flt(row.max_advance_amount),
			"unlimited": unlimited,
		}
	return limits


def designation_can_approve(designation, amount, settings=None):
	limits = get_designation_limit_map(settings)
	if not designation or designation not in limits:
		return False
	row = limits[designation]
	if row.get("unlimited"):
		return True
	return flt(amount) <= flt(row.get("max_approve_amount"))


def designation_advance_limit(designation, settings=None):
	limits = get_designation_limit_map(settings)
	if not designation or designation not in limits:
		return 0
	row = limits[designation]
	if row.get("unlimited"):
		return flt("inf") if False else 10**12
	return flt(row.get("max_advance_amount"))
