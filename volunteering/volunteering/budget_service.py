import frappe
from frappe import _
from frappe.utils import flt

from volunteering.volunteering.approval_routing import get_amount_field
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)

BUDGET_TRACKED_DOCTYPES = ("Expense Claim", "Purchase Order", "Purchase Invoice")
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


def get_document_amount(doc):
	return flt(doc.get(get_amount_field(doc.doctype)) or 0)


def get_consumed_amount(project, department, exclude=None):
	if not project or not department:
		return 0

	total = 0
	for doctype in BUDGET_TRACKED_DOCTYPES:
		total += _sum_doctype_amount(doctype, project, department, exclude)
	return total


def _sum_doctype_amount(doctype, project, department, exclude):
	amount_field = get_amount_field(doctype)
	filters = {
		"project": project,
		"department": department,
		"docstatus": ["!=", 2],
	}
	if frappe.db.has_column(doctype, "workflow_state"):
		filters["workflow_state"] = ["not in", list(EXCLUDED_WORKFLOW_STATES)]

	rows = frappe.get_all(doctype, filters=filters, fields=["name", amount_field])
	total = 0
	for row in rows:
		if exclude and exclude == (doctype, row.name):
			continue
		total += flt(row.get(amount_field))
	return total


def validate_budget_on_save(doc, method=None):
	if doc.doctype not in BUDGET_TRACKED_DOCTYPES:
		return

	settings = get_accounting_settings()
	if not settings.get("enable_budget_warnings"):
		return

	if not doc.get("project") or not doc.get("department"):
		return

	allocated = get_allocated_budget(doc.project, doc.department)
	if not allocated:
		return

	exclude = None if doc.is_new() else (doc.doctype, doc.name)
	consumed = get_consumed_amount(doc.project, doc.department, exclude=exclude)
	proposed = consumed + get_document_amount(doc)

	if proposed <= allocated:
		return

	over_by = proposed - allocated
	frappe.msgprint(
		_(
			"Department budget warning: {0} / {1} allocated for {2} on project {3}. "
			"This document would exceed the budget by {4}."
		).format(
			frappe.format_value(proposed, "Currency"),
			frappe.format_value(allocated, "Currency"),
			doc.department,
			doc.project,
			frappe.format_value(over_by, "Currency"),
		),
		indicator="orange",
		title=_("Budget Exceeded"),
	)


@frappe.whitelist()
def get_budget_health(project=None):
	"""Return department budget utilisation rows for a project or all projects."""
	frappe.has_permission("Project", "read", throw=True)

	projects = [project] if project else frappe.get_all("Project", pluck="name")
	rows = []

	for project_name in projects:
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
					"department": budget.department,
					"allocated": allocated,
					"consumed": consumed,
					"remaining": remaining,
					"utilisation_pct": (consumed / allocated * 100) if allocated else 0,
					"route": f"/app/project/{project_name}",
				}
			)

	return rows
