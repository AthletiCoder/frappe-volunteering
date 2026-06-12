import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from volunteering.volunteering.custom_fields import ACCOUNTING_CUSTOM_FIELDS

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


def reload_accounting_workflows():
	"""Reload EC/PO workflows from fixtures (used in tests after JSON changes)."""
	import json

	ensure_workflow_actions()
	path = frappe.get_app_path("volunteering", "fixtures", "workflow.json")
	with open(path) as handle:
		workflows = json.load(handle)

	for wf_data in workflows:
		if wf_data.get("document_type") not in ("Expense Claim", "Purchase Order"):
			continue
		name = wf_data["name"]
		if frappe.db.exists("Workflow", name):
			frappe.delete_doc("Workflow", name, ignore_permissions=True, force=True)
		frappe.get_doc(wf_data).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Workflow")
	sync_workflow_submit_permissions()


def after_migrate():
	setup_accounting_custom_fields()
	ensure_accounting_roles()
	ensure_workflow_actions()
	ensure_departments()
	ensure_accounting_settings()
	sync_workflow_submit_permissions()


def ensure_workflow_actions():
	for action_name in ("Escalate",):
		if frappe.db.exists("Workflow Action Master", action_name):
			continue
		frappe.get_doc(
			{"doctype": "Workflow Action Master", "workflow_action_name": action_name}
		).insert(ignore_permissions=True)


def sync_workflow_submit_permissions():
	"""Employees must submit their own documents (owner == submitter)."""
	for workflow_name in ("Expense Claim Approval", "Purchase Order Approval"):
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
			# Safe if another migrate/worker created the same department concurrently.
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
	settings.save(ignore_permissions=True)
