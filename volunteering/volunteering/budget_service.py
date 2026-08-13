# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.approval_routing import get_amount_field, get_document_amount
from volunteering.volunteering.authority import BOARD_OF_DIRECTORS, user_has_board_of_directors
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)

# PO commits budget; PI settles PO — do not double-count Purchase Invoice.
BUDGET_TRACKED_DOCTYPES = ("Expense Claim", "Purchase Order", "Employee Advance")
CLOSED_PROJECT_CHECK_DOCTYPES = BUDGET_TRACKED_DOCTYPES + ("Purchase Invoice",)
EXCLUDED_WORKFLOW_STATES = ("Draft", "Rejected", "")


def get_allocated_budget(project, department):
	if not project or not department:
		return 0

	for row in frappe.get_all(
		"Project Department Budget",
		filters={"parent": project, "parenttype": "Project", "department": department},
		fields=["allocated_amount"],
	):
		return flt(row.allocated_amount)
	return 0


def get_project_total_allocated(project):
	if not project:
		return 0
	total = 0
	for row in frappe.get_all(
		"Project Department Budget",
		filters={"parent": project, "parenttype": "Project"},
		fields=["allocated_amount"],
	):
		total += flt(row.allocated_amount)
	return total


def get_consumed_amount(project, department, exclude=None):
	if not project or not department:
		return 0

	total = 0
	for doctype in BUDGET_TRACKED_DOCTYPES:
		total += _sum_doctype_amount(doctype, project, department, exclude)
	return total


def _sum_doctype_amount(doctype, project, department, exclude):
	amount_field = get_amount_field(doctype)
	if not frappe.db.has_column(doctype, amount_field):
		return 0
	if not frappe.db.has_column(doctype, "project"):
		return 0

	filters = {
		"project": project,
		"docstatus": ["!=", 2],
	}
	if frappe.db.has_column(doctype, "department"):
		filters["department"] = department
	if frappe.db.has_column(doctype, "workflow_state"):
		filters["workflow_state"] = ["not in", list(EXCLUDED_WORKFLOW_STATES)]

	rows = frappe.get_all(doctype, filters=filters, fields=["name", amount_field])
	total = 0
	for row in rows:
		if exclude and exclude == (doctype, row.name):
			continue
		total += flt(row.get(amount_field))
	return total


def _overspend_pct(allocated, proposed):
	if allocated <= 0:
		return 0
	if proposed <= allocated:
		return 0
	return ((proposed - allocated) / allocated) * 100


def _is_approving(doc):
	"""True when this save is transitioning into Approved."""
	if doc.workflow_state != "Approved":
		return False
	previous = doc.get_doc_before_save()
	if not previous:
		return True
	return previous.workflow_state != "Approved"


def _can_override_budget(settings=None):
	"""Board of Directors grade overrides; an optional configured role still works."""
	if user_has_board_of_directors(frappe.session.user):
		return True
	settings = settings or get_accounting_settings()
	override_role = settings.get("budget_override_role")
	return bool(override_role) and override_role in frappe.get_roles(frappe.session.user)


# Legacy alias for callers/tests still on the role-only name.
_has_budget_override_role = _can_override_budget


def validate_budget_on_save(doc, method=None):
	if doc.doctype not in CLOSED_PROJECT_CHECK_DOCTYPES:
		return

	if not doc.get("project"):
		return

	budget_status = frappe.db.get_value("Project", doc.project, "budget_status")
	if budget_status == "Closed":
		frappe.throw(_("Project {0} budget is Closed. Choose an Active project.").format(doc.project))

	if doc.doctype not in BUDGET_TRACKED_DOCTYPES:
		return

	if not doc.get("department"):
		return

	settings = get_accounting_settings()
	allocated = get_allocated_budget(doc.project, doc.department)
	if not allocated:
		return

	exclude = None if doc.is_new() else (doc.doctype, doc.name)
	consumed = get_consumed_amount(doc.project, doc.department, exclude=exclude)
	proposed = consumed + get_document_amount(doc)
	over_pct = _overspend_pct(allocated, proposed)

	if proposed <= allocated:
		refresh_project_budget_status(doc.project)
		return

	over_by = proposed - allocated
	warning = _(
		"Department budget warning: {0} / {1} allocated for {2} on project {3}. "
		"This document would exceed the budget by {4} ({5}%)."
	).format(
		frappe.format_value(proposed, "Currency"),
		frappe.format_value(allocated, "Currency"),
		doc.department,
		doc.project,
		frappe.format_value(over_by, "Currency"),
		frappe.utils.rounded(over_pct, 1),
	)

	hard_pct = flt(settings.get("budget_hard_block_pct") or 25)
	reason = (doc.get("budget_override_reason") or "").strip()
	override_authority = settings.get("budget_override_role") or BOARD_OF_DIRECTORS

	if _is_approving(doc):
		if not reason:
			frappe.throw(
				_(
					"{0} Enter a Budget Exceedance Reason explaining why this department "
					"is going over the approved budget, then Approve again."
				).format(warning),
				title=_("Budget Exceedance Reason Required"),
			)

		if over_pct > hard_pct and not _can_override_budget(settings):
			frappe.throw(
				_(
					"{0} Overspend is {1}% (hard limit {2}%). "
					"Escalate to {3} to Approve with a Budget Exceedance Reason."
				).format(
					warning,
					frappe.utils.rounded(over_pct, 1),
					hard_pct,
					override_authority,
				),
				title=_("Budget Hard Block"),
			)

		frappe.msgprint(
			_("Budget exceedance recorded: {0}").format(reason),
			indicator="orange",
			title=_("Budget Exceedance Applied"),
		)
		refresh_project_budget_status(doc.project)
		return

	if settings.get("enable_budget_warnings"):
		frappe.msgprint(warning, indicator="orange", title=_("Budget Exceeded"))

	refresh_project_budget_status(doc.project)


def refresh_project_budget_status(project):
	"""Mark Exhausted when any department is fully consumed; else Active (unless Closed)."""
	if not project or not frappe.db.has_column("Project", "budget_status"):
		return
	current = frappe.db.get_value("Project", project, "budget_status")
	if current == "Closed":
		return

	exhausted = False
	for row in frappe.get_all(
		"Project Department Budget",
		filters={"parent": project, "parenttype": "Project"},
		fields=["department", "allocated_amount"],
	):
		allocated = flt(row.allocated_amount)
		if allocated and get_consumed_amount(project, row.department) >= allocated:
			exhausted = True
			break

	new_status = "Exhausted" if exhausted else "Active"
	if current != new_status:
		frappe.db.set_value("Project", project, "budget_status", new_status, update_modified=False)


def validate_project_department_budgets(doc, method=None):
	"""Reject duplicate department rows on Project."""
	seen = set()
	for row in doc.get("department_budgets") or []:
		department = row.get("department")
		if not department:
			continue
		if department in seen:
			frappe.throw(
				_("Department {0} appears more than once in Department Budgets.").format(department),
				title=_("Duplicate Department Budget"),
			)
		seen.add(department)


@frappe.whitelist()
def get_budget_health(project=None):
	"""Return department budget utilisation rows for a project or all projects."""
	frappe.has_permission("Project", "read", throw=True)

	filters = {}
	if project:
		filters["name"] = project
	projects = frappe.get_all(
		"Project", filters=filters, fields=["name", "project_type", "budget_status"]
	)
	rows = []

	for project_row in projects:
		project_name = project_row.name
		budget_rows = frappe.get_all(
			"Project Department Budget",
			filters={"parent": project_name, "parenttype": "Project"},
			fields=["department", "allocated_amount"],
		)
		for budget in budget_rows:
			allocated = flt(budget.allocated_amount)
			consumed = get_consumed_amount(project_name, budget.department)
			remaining = allocated - consumed
			rows.append(
				{
					"project": project_name,
					"project_type": project_row.get("project_type"),
					"budget_status": project_row.get("budget_status"),
					"department": budget.department,
					"allocated": allocated,
					"consumed": consumed,
					"remaining": remaining,
					"utilisation_pct": (consumed / allocated * 100) if allocated else 0,
					"route": f"/app/project/{project_name}",
				}
			)

	return rows
