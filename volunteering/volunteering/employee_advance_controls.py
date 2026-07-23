# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee Advance NGO rules on top of HRMS."""

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	designation_advance_limit,
	get_accounting_settings,
)

# Fully settled statuses never block replenishment
SETTLED_STATUSES = ("Claimed", "Returned", "Cancelled")


def before_employee_advance_save(doc, method=None):
	if not doc.get("project"):
		frappe.throw(_("Project is required on Employee Advance."))

	_validate_max_unsettled(doc)
	_validate_designation_advance_limit(doc)


def advance_residual_amount(row) -> float:
	"""Unsettled balance on an Employee Advance row/dict."""
	advance_amount = flt(row.get("advance_amount"))
	paid_amount = flt(row.get("paid_amount"))
	claimed_amount = flt(row.get("claimed_amount"))
	return_amount = flt(row.get("return_amount"))
	status = row.get("status") or ""

	if status in SETTLED_STATUSES or status == "Cancelled":
		return 0.0

	# Not yet disbursed: treat full request as residual
	if paid_amount <= 0:
		return advance_amount

	return max(paid_amount - claimed_amount - return_amount, 0.0)


def advance_residual_ratio(row) -> float:
	"""Residual as fraction of paid (or advance) amount. 0 = settled."""
	residual = advance_residual_amount(row)
	if residual <= 0:
		return 0.0

	paid_amount = flt(row.get("paid_amount"))
	advance_amount = flt(row.get("advance_amount"))
	base = paid_amount if paid_amount > 0 else advance_amount
	if base <= 0:
		return 0.0
	return residual / base


def is_blocking_advance(row, replenish_pct: float) -> bool:
	"""True when residual exceeds replenish threshold (default 10%)."""
	if (row.get("status") or "") in SETTLED_STATUSES:
		return False
	threshold = flt(replenish_pct) / 100.0
	if threshold < 0:
		threshold = 0.0
	return advance_residual_ratio(row) > threshold


def list_open_advances_for_employee(employee, exclude_name=None):
	filters = {
		"employee": employee,
		"docstatus": ["!=", 2],
	}
	rows = frappe.get_all(
		"Employee Advance",
		filters=filters,
		fields=[
			"name",
			"status",
			"advance_amount",
			"paid_amount",
			"claimed_amount",
			"return_amount",
			"docstatus",
		],
	)
	if exclude_name:
		rows = [r for r in rows if r.name != exclude_name]
	return rows


def _validate_max_unsettled(doc):
	settings = get_accounting_settings()
	max_open = int(settings.get("max_unsettled_advances") or 1)
	if max_open <= 0:
		return

	replenish_pct = flt(settings.get("advance_replenish_residual_pct"))
	if settings.get("advance_replenish_residual_pct") is None:
		replenish_pct = 10.0

	rows = list_open_advances_for_employee(doc.employee, exclude_name=doc.name)
	blocking = [r for r in rows if is_blocking_advance(r, replenish_pct)]
	non_blocking_residual = [
		r for r in rows if advance_residual_amount(r) > 0 and not is_blocking_advance(r, replenish_pct)
	]

	if len(blocking) >= max_open:
		frappe.throw(
			_(
				"Employee {0} already has {1} unsettled advance(s) with residual above {2}%. "
				"Settle or return the previous advance before requesting a new one."
			).format(doc.employee, len(blocking), flt(replenish_pct, 2)),
			title=_("Unsettled Advance Exists"),
		)

	if non_blocking_residual:
		parts = []
		for r in non_blocking_residual:
			parts.append(
				_("{0}: residual {1}").format(
					r.name,
					frappe.format_value(advance_residual_amount(r), "Currency"),
				)
			)
		frappe.msgprint(
			_(
				"Replenishing while prior advance(s) still have a small residual (≤{0}%). "
				"Please claim or return these leftovers: {1}"
			).format(flt(replenish_pct, 2), "; ".join(parts)),
			title=_("Advance Residual Reminder"),
			indicator="orange",
		)


def residual_advances_for_employee(employee):
	"""Open advances with any residual > 0 (for PE warnings / lists)."""
	settings = get_accounting_settings()
	rows = list_open_advances_for_employee(employee)
	return [
		{
			"name": r.name,
			"residual": advance_residual_amount(r),
			"ratio": advance_residual_ratio(r),
			"status": r.status,
		}
		for r in rows
		if advance_residual_amount(r) > 0
	]


def _validate_designation_advance_limit(doc):
	designation = frappe.db.get_value("Employee", doc.employee, "designation")
	limit = designation_advance_limit(designation)
	amount = flt(doc.advance_amount)
	if not designation:
		return
	# Board unlimited uses large sentinel
	if limit >= 10**11:
		return
	if amount > limit:
		frappe.throw(
			_(
				"Advance amount {0} exceeds the designation limit ({1}) for {2}."
			).format(
				frappe.format_value(amount, "Currency"),
				frappe.format_value(limit, "Currency"),
				designation,
			),
			title=_("Advance Limit Exceeded"),
		)
