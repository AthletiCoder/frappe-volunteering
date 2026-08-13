# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt

from volunteering.volunteering.authority import BOARD_OF_DIRECTORS

# (Employee Grade, max approve for others, max self advance)
DEFAULT_GRADE_LIMITS = (
	("Associate", 0, 2000),
	("Manager", 2000, 5000),
	("Vice President", 5000, 10000),
	("President", 10000, 15000),
	("Director", 25000, 50000),
	("CEO", 50000, 50000),
	("Executive Board", 100000, 100000),
	("Board of Directors", 0, 0),  # 0 approve = unlimited when flagged below
)

UNLIMITED_GRADES = frozenset({BOARD_OF_DIRECTORS})

# Legacy aliases — limits moved from Designation to Employee Grade.
DEFAULT_DESIGNATION_LIMITS = DEFAULT_GRADE_LIMITS
UNLIMITED_DESIGNATIONS = UNLIMITED_GRADES


class VolunteeringAccountingSettings(Document):
	pass


def get_accounting_settings():
	"""Return accounting settings with defaults if not yet created."""
	if frappe.db.exists("DocType", "Volunteering Accounting Settings"):
		return frappe.get_cached_doc("Volunteering Accounting Settings")
	return frappe._dict(
		tier_1_limit=2000,
		tier_2_limit=10000,
		use_grade_approval=1,
		use_designation_approval=1,
		vendor_payment_threshold=5000,
		cash_payment_limit=2000,
		invoice_split_window_days=7,
		max_unsettled_advances=1,
		advance_replenish_residual_pct=10,
		enable_budget_warnings=1,
		budget_hard_block_pct=25,
		budget_override_role="",
		emergency_submit_working_days=1,
		emergency_approve_working_days=2,
		preferred_payout_mode="Manual",
		payout_provider="manual",
	)


def get_limit_rows(settings=None):
	"""Saved grade-limit rows.

	If a settings object with `designation_limits` is passed (tests inject
	these), use it; otherwise read the Approval and Advance Limits single.
	The child fieldname stays `designation`; its values are Employee Grades.
	"""
	if settings is not None and settings.get("designation_limits"):
		return settings.get("designation_limits")

	if frappe.db.exists("DocType", "Approval and Advance Limits"):
		return frappe.get_cached_doc("Approval and Advance Limits").get("designation_limits") or []

	return []


def get_grade_limit_map(settings=None):
	"""Return {grade_name: {max_approve_amount, max_advance_amount, unlimited}}.

	Starts from DEFAULT_GRADE_LIMITS, then overlays saved rows from the
	Approval and Advance Limits page.
	"""
	limits = {}
	for grade, max_approve, max_advance in DEFAULT_GRADE_LIMITS:
		limits[grade] = {
			"max_approve_amount": flt(max_approve),
			"max_advance_amount": flt(max_advance),
			"unlimited": grade in UNLIMITED_GRADES,
		}
	for row in get_limit_rows(settings):
		if not row.designation:
			continue
		limits[row.designation] = {
			"max_approve_amount": flt(row.max_approve_amount),
			"max_advance_amount": flt(row.max_advance_amount),
			"unlimited": row.designation in UNLIMITED_GRADES,
		}
	return limits


def grade_can_approve(grade, amount, settings=None):
	limits = get_grade_limit_map(settings)
	if not grade or grade not in limits:
		return False
	row = limits[grade]
	if row.get("unlimited"):
		return True
	return flt(amount) <= flt(row.get("max_approve_amount"))


def grade_advance_limit(grade, settings=None):
	limits = get_grade_limit_map(settings)
	if not grade:
		return 0
	if grade not in limits:
		# Unknown grade: do not hard-block at 0 — treat as unset
		return None
	row = limits[grade]
	if row.get("unlimited"):
		return 10**12
	return flt(row.get("max_advance_amount"))


# --- Legacy wrappers (call sites migrating from Designation to Grade) -------


def get_designation_limit_map(settings=None):
	return get_grade_limit_map(settings)


def designation_can_approve(designation, amount, settings=None):
	return grade_can_approve(designation, amount, settings)


def designation_advance_limit(designation, settings=None):
	return grade_advance_limit(designation, settings)
