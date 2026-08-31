# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee Advance NGO rules on top of HRMS."""

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
	grade_advance_limit,
)

# Fully settled statuses never block replenishment
SETTLED_STATUSES = ("Claimed", "Returned", "Cancelled")


def before_employee_advance_save(doc, method=None):
	from volunteering.volunteering.employee_advance_permissions import validate_employee_self_only

	validate_employee_self_only(doc, method)
	# Advances are staff float, not program spend. Do not tag to a Project.
	# Budget is checked on the Expense Claim (or PO) that settles the spend.
	if doc.get("project"):
		doc.project = None

	_ensure_currency(doc)
	_ensure_advance_account(doc)
	_validate_max_unsettled(doc)
	_validate_grade_advance_limit(doc)


def _ensure_currency(doc):
	if doc.get("currency"):
		return
	company = doc.get("company")
	if not company and doc.get("employee"):
		company = frappe.db.get_value("Employee", doc.employee, "company")
	if company:
		doc.currency = frappe.db.get_value("Company", company, "default_currency") or "INR"
	else:
		doc.currency = "INR"


def _ensure_advance_account(doc):
	if doc.get("advance_account") or not doc.get("employee"):
		return
	account = frappe.db.get_value("Employee", doc.employee, "employee_advance_account")
	if not account and doc.get("company"):
		account = frappe.db.get_value(
			"Company", doc.company, "default_employee_advance_account"
		)
	if account:
		doc.advance_account = account


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


@frappe.whitelist()
def get_grade_advance_limit_for_employee(employee):
	"""Max self-service advance for the employee's grade (for Desk form hint)."""
	from volunteering.volunteering.approval_routing import get_approval_band_for_employee

	if not employee:
		return {}
	grade = get_approval_band_for_employee(employee)
	if not grade:
		return {"grade": None, "limit": None, "label": ""}
	limit = grade_advance_limit(grade)
	if limit is None:
		return {"grade": grade, "limit": None, "label": _("No advance limit configured for {0}.").format(grade)}
	if limit >= 10**11:
		return {
			"grade": grade,
			"limit": None,
			"label": _("No self-service advance cap for {0}.").format(grade),
		}
	return {
		"grade": grade,
		"limit": limit,
		"label": _("Max self advance for {0}: {1}").format(
			grade, frappe.format_value(limit, "Currency")
		),
	}


@frappe.whitelist()
def get_linkable_advances_hint(employee):
	"""Explain why Get Advances may be empty (must be submitted + paid)."""
	if not employee:
		return ""

	rows = frappe.get_all(
		"Employee Advance",
		filters={"employee": employee, "docstatus": ["!=", 2]},
		fields=["name", "docstatus", "paid_amount", "status", "workflow_state"],
	)
	if not rows:
		return _(
			"No Employee Advances found for this employee. Create and get an advance paid before linking."
		)

	linkable = [
		r
		for r in rows
		if r.docstatus == 1
		and flt(r.paid_amount) > 0
		and (r.status or "") not in ("Claimed", "Returned", "Partly Claimed and Returned")
	]
	if linkable:
		names = ", ".join(r.name for r in linkable[:5])
		return _("Advances available to link via Get Advances: {0}").format(names)

	parts = []
	for r in rows[:5]:
		if r.docstatus != 1:
			parts.append(_("{0}: not submitted yet").format(r.name))
		elif flt(r.paid_amount) <= 0:
			parts.append(_("{0}: approved but not paid by Accounts yet").format(r.name))
		else:
			parts.append(_("{0}: already {1}").format(r.name, r.status or _("settled")))

	return _(
		"No advances qualify for Get Advances yet (needs Submitted + Paid amount > 0 + not fully claimed). "
		"{0}"
	).format("; ".join(parts))


def _validate_grade_advance_limit(doc):
	from volunteering.volunteering.approval_routing import get_approval_band_for_employee

	grade = get_approval_band_for_employee(doc.employee)
	if not grade:
		return

	limit = grade_advance_limit(grade)
	amount = flt(doc.advance_amount)
	# None = grade not configured — skip hard block
	if limit is None:
		return
	# Board unlimited uses large sentinel
	if limit >= 10**11:
		return
	if amount > limit:
		frappe.throw(
			_("Advance amount {0} exceeds the grade limit ({1}) for {2}.").format(
				frappe.format_value(amount, "Currency"),
				frappe.format_value(limit, "Currency"),
				grade,
			),
			title=_("Advance Limit Exceeded"),
		)
