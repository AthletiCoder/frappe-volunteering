import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from volunteering.volunteering.custom_fields import ACCOUNTING_CUSTOM_FIELDS
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	DEFAULT_DESIGNATION_LIMITS,
)

DEPARTMENT_NAMES = [
	"Procurement",
	"Operations",
	"Admin",
	"HR",
	"Media",
	"Accounts",
	"Donor Relations",
]

ACCOUNTING_ROLES = [
	"NGO Department Head",
	"NGO Board Member",
	"NGO Board Chairperson",
]

DEFAULT_DESIGNATIONS = [row[0] for row in DEFAULT_DESIGNATION_LIMITS]


def reload_accounting_workflows():
	"""Reload EC/PO/EA workflows from fixtures (used in tests after JSON changes)."""
	import json

	ensure_workflow_actions()
	ensure_workflow_states()
	path = frappe.get_app_path("volunteering", "fixtures", "workflow.json")
	with open(path) as handle:
		workflows = json.load(handle)

	for wf_data in workflows:
		if wf_data.get("document_type") not in (
			"Expense Claim",
			"Purchase Order",
			"Employee Advance",
			"Purchase Invoice",
		):
			continue
		name = wf_data["name"]
		if frappe.db.exists("Workflow", name):
			frappe.delete_doc("Workflow", name, ignore_permissions=True, force=True)
		frappe.get_doc(wf_data).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Workflow")
	sync_workflow_submit_permissions()


def after_migrate():
	setup_accounting_custom_fields()
	remove_obsolete_accounting_custom_fields()
	ensure_project_types()
	ensure_accounting_roles()
	ensure_workflow_actions()
	ensure_workflow_states()
	ensure_departments()
	ensure_designations()
	ensure_accounting_settings()
	reload_accounting_workflows()
	sync_workflow_submit_permissions()
	from volunteering.volunteering.accounting_dashboard.setup import ensure_accounting_pages
	from volunteering.volunteering.wiki_setup import ensure_help_wikis

	ensure_accounting_pages()
	ensure_help_wikis()


PROJECT_TYPES = ("Campaign", "Event", "Admin")


def ensure_project_types():
	if not frappe.db.exists("DocType", "Project Type"):
		return
	for name in PROJECT_TYPES:
		if frappe.db.exists("Project Type", name):
			continue
		frappe.get_doc({"doctype": "Project Type", "project_type": name}).insert(
			ignore_permissions=True
		)


def remove_obsolete_accounting_custom_fields():
	"""Drop fields superseded by native Project Type / HRMS department."""
	for fieldname in (
		"Project-fund_project_type",
		"Expense Claim-department",
	):
		if frappe.db.exists("Custom Field", fieldname):
			frappe.delete_doc("Custom Field", fieldname, ignore_permissions=True, force=True)


def ensure_workflow_actions():
	for action_name in ("Escalate",):
		if frappe.db.exists("Workflow Action Master", action_name):
			continue
		frappe.get_doc(
			{"doctype": "Workflow Action Master", "workflow_action_name": action_name}
		).insert(ignore_permissions=True)


def ensure_workflow_states():
	if frappe.db.exists("Workflow State", "Pending Approval"):
		return
	frappe.get_doc(
		{
			"doctype": "Workflow State",
			"workflow_state_name": "Pending Approval",
			"style": "Warning",
			"icon": "question-sign",
		}
	).insert(ignore_permissions=True)


def sync_workflow_submit_permissions():
	"""Employees must submit their own documents (owner == submitter)."""
	for workflow_name in (
		"Expense Claim Approval",
		"Purchase Order Approval",
		"Employee Advance Approval",
		"Purchase Invoice Workflow",
	):
		if not frappe.db.exists("Workflow", workflow_name):
			continue

		workflow = frappe.get_doc("Workflow", workflow_name)
		changed = False
		for transition in workflow.transitions:
			if transition.action in ("Submit", "Re-submit") and not transition.allow_self_approval:
				transition.allow_self_approval = 1
				changed = True
		if changed:
			workflow.save(ignore_permissions=True)


def setup_accounting_custom_fields():
	create_custom_fields(ACCOUNTING_CUSTOM_FIELDS, ignore_validate=True)


def ensure_accounting_roles():
	for role_name in ACCOUNTING_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc({"doctype": "Role", "role_name": role_name, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def ensure_designations():
	for name in DEFAULT_DESIGNATIONS:
		if frappe.db.exists("Designation", name):
			continue
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(
			ignore_permissions=True
		)


def _department_exists(department_name, company=None):
	"""Match by label + company; ERPNext names docs like 'Operations - SF'."""
	filters = {"department_name": department_name}
	if company:
		filters["company"] = company
	return frappe.db.exists("Department", filters)


def ensure_departments():
	company = frappe.db.get_value("Company", {}, "name")
	for department_name in DEPARTMENT_NAMES:
		if _department_exists(department_name, company):
			continue

		doc = {"doctype": "Department", "department_name": department_name}
		if company:
			doc["company"] = company
		try:
			frappe.get_doc(doc).insert(ignore_permissions=True)
		except frappe.DuplicateEntryError:
			continue


def ensure_accounting_settings():
	if not frappe.db.exists("DocType", "Volunteering Accounting Settings"):
		return

	settings = frappe.get_single("Volunteering Accounting Settings")
	if not settings.tier_1_limit:
		settings.tier_1_limit = 2000
	if not settings.tier_2_limit:
		settings.tier_2_limit = 10000
	if settings.post_facto_max_days is None:
		settings.post_facto_max_days = 7
	if settings.post_facto_max_per_month is None:
		settings.post_facto_max_per_month = 2
	if settings.get("vendor_payment_threshold") is None:
		settings.vendor_payment_threshold = 5000
	if settings.get("cash_payment_limit") is None:
		settings.cash_payment_limit = 2000
	if settings.get("invoice_split_window_days") is None:
		settings.invoice_split_window_days = 7
	if settings.get("max_unsettled_advances") is None:
		settings.max_unsettled_advances = 1
	if settings.get("advance_replenish_residual_pct") is None:
		settings.advance_replenish_residual_pct = 10
	if settings.get("budget_hard_block_pct") is None:
		settings.budget_hard_block_pct = 25
	if not settings.get("budget_override_role"):
		settings.budget_override_role = "NGO Board Chairperson"
	if settings.get("emergency_submit_working_days") is None:
		settings.emergency_submit_working_days = 1
	if settings.get("emergency_approve_working_days") is None:
		settings.emergency_approve_working_days = 2
	if settings.get("use_designation_approval") is None:
		settings.use_designation_approval = 1
	if not settings.get("payout_provider"):
		settings.payout_provider = "manual"
	if not settings.get("preferred_payout_mode"):
		settings.preferred_payout_mode = "Manual"

	if not settings.get("designation_limits"):
		for designation, max_approve, max_advance in DEFAULT_DESIGNATION_LIMITS:
			settings.append(
				"designation_limits",
				{
					"designation": designation,
					"max_approve_amount": max_approve,
					"max_advance_amount": max_advance,
				},
			)

	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Volunteering Accounting Settings")
