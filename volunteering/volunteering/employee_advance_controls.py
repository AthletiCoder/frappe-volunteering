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
	_autoset_project(doc)
	if not doc.get("project"):
		frappe.throw(
			_(
				"Project could not be determined for this advance. "
				"Set a default Admin project on Volunteering Accounting Settings, "
				"or ask Accounts to assign a project."
			)
		)

	_validate_max_unsettled(doc)
	_validate_grade_advance_limit(doc)


def _autoset_project(doc):
	"""Keep project for budget tracking but hide it from employees."""
	if doc.get("project"):
		return

	settings = get_accounting_settings()
	default_project = settings.get("default_advance_project") if settings else None
	if default_project and frappe.db.exists("Project", default_project):
		doc.project = default_project
		return

	# Prefer an Active Admin project for the company
	company = doc.get("company") or frappe.db.get_value("Employee", doc.employee, "company")
	filters = {"status": "Open", "project_type": "Admin"}
	if company and frappe.db.has_column("Project", "company"):
		filters["company"] = company
	admin_project = frappe.db.get_value("Project", filters, "name", order_by="modified desc")
	if admin_project:
		doc.project = admin_project
		return

	# Last resort: any Open project for the company
	fallback_filters = {"status": "Open"}
	if company and frappe.db.has_column("Project", "company"):
		fallback_filters["company"] = company
	doc.project = frappe.db.get_value("Project", fallback_filters, "name", order_by="modified desc")


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
