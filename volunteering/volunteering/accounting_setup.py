import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import cint, flt

from volunteering.volunteering.custom_fields import ACCOUNTING_CUSTOM_FIELDS
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	DEFAULT_GRADE_LIMITS,
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

# Authority is Employee Grade + Department.department_head; no board roles to seed.
ACCOUNTING_ROLES: list[str] = []

BUDGET_HEALTH_ROLES = (
	"Accounts User",
	"Accounts Manager",
	"NGO Coordinator",
)

DEFAULT_GRADES = [row[0] for row in DEFAULT_GRADE_LIMITS]
# Job titles seeded historically; kept so existing Employee.designation links resolve.
DEFAULT_DESIGNATIONS = DEFAULT_GRADES


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
		doc = frappe.get_doc(wf_data)
		# Masters are seeded above; ignore_links covers racey/partial Cloud sites.
		doc.flags.ignore_links = True
		doc.insert(ignore_permissions=True)

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
	ensure_employee_grades()
	ensure_accounting_settings()
	ensure_designation_limits()
	ensure_employee_advance_accounts()
	ensure_expense_claim_payable_account()
	from volunteering.volunteering.donation_accounting_setup import ensure_donation_accounting

	ensure_donation_accounting()
	ensure_employee_advance_field_visibility()
	ensure_expense_claim_field_visibility()
	ensure_manager_advance_field_labels()
	ensure_approval_routing_section_break()
	ensure_budget_health_permissions()
	from volunteering.volunteering.employee_spending_permissions import (
		ensure_employee_self_service_permissions,
	)

	ensure_employee_self_service_permissions()
	reload_accounting_workflows()
	sync_workflow_submit_permissions()
	from volunteering.volunteering.accounting_dashboard.setup import ensure_accounting_pages
	from volunteering.volunteering.wiki_setup import ensure_help_wikis

	ensure_accounting_pages()
	ensure_help_wikis()


def ensure_approval_routing_section_break():
	"""Approval & Routing must be a Section Break, not a Tab Break.

	A Tab Break on Expense Claim / Employee Advance / Purchase Order left Desk
	forms blank for staff (both tab panes stayed ``hide`` after refresh).
	"""
	for doctype in ("Expense Claim", "Purchase Order", "Employee Advance"):
		name = frappe.db.get_value(
			"Custom Field",
			{"dt": doctype, "fieldname": "approval_routing_tab"},
			"name",
		)
		if not name:
			continue
		current = frappe.db.get_value("Custom Field", name, ["fieldtype", "collapsible"], as_dict=True)
		if current and current.fieldtype == "Section Break" and cint(current.collapsible) == 1:
			continue
		frappe.db.set_value(
			"Custom Field",
			name,
			{"fieldtype": "Section Break", "collapsible": 1},
			update_modified=False,
		)
		frappe.clear_cache(doctype=doctype)


def ensure_manager_advance_field_labels():
	"""User-facing copy uses Manager's Advance (not float)."""
	updates = (
		("manager_float_holder", "Manager", "eval:doc.reimbursement_source=='Manager Advance'", None),
		(
			"manager_float_advance",
			"Manager's Advance",
			"eval:doc.reimbursement_source=='Manager Advance'",
			(
				"Suggested from your manager's paid advances with residual. "
				"Final settlement may use a different advance if the claim amount requires it."
			),
		),
	)
	for fieldname, label, depends_on, description in updates:
		name = frappe.db.get_value(
			"Custom Field",
			{"dt": "Expense Claim", "fieldname": fieldname},
			"name",
		)
		if not name:
			continue
		values = {"label": label, "depends_on": depends_on}
		if description is not None:
			values["description"] = description
		frappe.db.set_value("Custom Field", name, values, update_modified=False)
	frappe.clear_cache(doctype="Expense Claim")


def ensure_budget_health_permissions():
	"""Let roles allowed on Budget Health read its linked master records."""
	from frappe.permissions import add_permission, update_permission_property

	for doctype in ("Project", "Department"):
		if not frappe.db.exists("DocType", doctype):
			continue
		for role in BUDGET_HEALTH_ROLES:
			if not frappe.db.exists("Role", role):
				continue
			if not frappe.db.exists(
				"Custom DocPerm",
				{"parent": doctype, "role": role, "permlevel": 0, "if_owner": 0},
			):
				add_permission(doctype, role, permlevel=0, ptype="read")
			for permission_type in ("read", "select", "report"):
				update_permission_property(
					doctype,
					role,
					0,
					permission_type,
					1,
					validate=False,
				)
		frappe.clear_cache(doctype=doctype)


def ensure_employee_advance_accounts():
	"""Ensure each Company has a dedicated Employee Advances receivable and backfill Employees."""
	if not frappe.db.exists("DocType", "Account"):
		return

	for company in frappe.get_all("Company", pluck="name"):
		account = _ensure_employee_advance_account(company)
		if not account:
			continue
		if frappe.db.has_column("Company", "default_employee_advance_account"):
			current = frappe.db.get_value("Company", company, "default_employee_advance_account")
			if current != account:
				frappe.db.set_value(
					"Company", company, "default_employee_advance_account", account, update_modified=False
				)
		_backfill_employee_advance_accounts(company, account)


def _ensure_employee_advance_account(company: str) -> str | None:
	existing = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"account_name": "Employee Advances",
			"is_group": 0,
		},
		"name",
	)
	if existing:
		return existing

	# Prefer company default if already set and looks correct
	if frappe.db.has_column("Company", "default_employee_advance_account"):
		default = frappe.db.get_value("Company", company, "default_employee_advance_account")
		if default and frappe.db.exists("Account", default):
			acc = frappe.db.get_value(
				"Account", default, ["account_name", "account_type"], as_dict=True
			)
			if acc and acc.account_type == "Receivable" and "debtor" not in (acc.account_name or "").lower():
				return default

	parent = frappe.db.get_value(
		"Account",
		{
			"company": company,
			"is_group": 1,
			"root_type": "Asset",
			"account_type": "Receivable",
		},
		"name",
		order_by="lft asc",
	)
	if not parent:
		parent = frappe.db.get_value(
			"Account",
			{"company": company, "is_group": 1, "root_type": "Asset"},
			"name",
			order_by="lft asc",
		)
	if not parent:
		frappe.log_error(
			title="Employee Advances account skipped",
			message=f"No Asset parent account for company {company}",
		)
		return None

	doc = frappe.get_doc(
		{
			"doctype": "Account",
			"account_name": "Employee Advances",
			"company": company,
			"parent_account": parent,
			"is_group": 0,
			"root_type": "Asset",
			"report_type": "Balance Sheet",
			"account_type": "Receivable",
			"account_currency": frappe.db.get_value("Company", company, "default_currency"),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _backfill_employee_advance_accounts(company: str, account: str):
	if not frappe.db.has_column("Employee", "employee_advance_account"):
		return
	employees = frappe.get_all(
		"Employee",
		filters={"company": company, "status": "Active"},
		fields=["name", "employee_advance_account"],
	)
	for row in employees:
		current = row.employee_advance_account
		if current == account:
			continue
		# Replace empty or Debtors-like accounts
		replace = not current
		if current:
			acc_name = frappe.db.get_value("Account", current, "account_name") or ""
			if "debtor" in acc_name.lower():
				replace = True
		if replace:
			frappe.db.set_value(
				"Employee", row.name, "employee_advance_account", account, update_modified=False
			)


def ensure_employee_advance_field_visibility():
	"""Hide advance_account from non-Accounts; keep project hidden (advances are not tagged)."""
	_ensure_property_setter(
		"Employee Advance",
		"employee",
		"ignore_user_permissions",
		"1",
		"Check",
	)
	_ensure_property_setter(
		"Employee Advance",
		"advance_account",
		"hidden",
		"1",
		"Check",
	)
	_ensure_property_setter(
		"Employee Advance",
		"project",
		"hidden",
		"1",
		"Check",
	)
	# Project is unused on advances; budget is tagged on the settling Expense Claim.
	_ensure_property_setter(
		"Employee Advance",
		"project",
		"reqd",
		"0",
		"Check",
	)
	_ensure_property_setter(
		"Employee Advance",
		"currency_section",
		"collapsed",
		"1",
		"Check",
	)


def ensure_expense_claim_field_visibility():
	"""Hide GL accounts from staff; ignore User Permissions on Link fields.

	Employees get a User Permission on their own Employee (and Company). Any other
	Employee/User/Project/… Link on the claim then blocks *read* of their own
	document (e.g. manager_float_holder → manager).

	``employee`` must ignore UP too: Accounts users are Employees, so apply-to-all
	Employee UP would empty their Expense Claim list. Row scope is
	``expense_claim_permissions`` (own / approver / dept head / accounts).
	"""
	for doctype, fieldname in (
		("Expense Claim", "employee"),
		("Expense Claim", "payable_account"),
		("Expense Claim", "project"),
		("Expense Claim", "department"),
		("Expense Claim", "cost_center"),
		("Expense Claim", "expense_approver"),
		("Expense Claim", "pending_approver"),
		("Expense Claim", "manager_float_holder"),
		("Expense Claim", "manager_float_advance"),
		("Expense Claim", "currency"),
		("Expense Claim Advance", "advance_account"),
		("Expense Claim Advance", "employee_advance"),
		("Expense Claim Detail", "default_account"),
		("Expense Claim Detail", "cost_center"),
		("Expense Claim Detail", "expense_type"),
		("Expense Claim Detail", "project"),
	):
		if not frappe.db.exists("DocType", doctype):
			continue
		if not frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname}) and not frappe.db.exists(
			"Custom Field", {"dt": doctype, "fieldname": fieldname}
		):
			continue
		_ensure_property_setter(doctype, fieldname, "ignore_user_permissions", "1", "Check")

	_ensure_property_setter("Expense Claim Detail", "default_account", "hidden", "1", "Check")
	_ensure_property_setter(
		"Expense Claim",
		"payable_account",
		"hidden",
		"1",
		"Check",
	)
	_ensure_property_setter(
		"Expense Claim",
		"payable_account",
		"read_only",
		"1",
		"Check",
	)


def _ensure_property_setter(doctype, fieldname, property_name, value, property_type):
	name = f"{doctype}-{fieldname}-{property_name}"
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, "value", value, update_modified=False)
		return
	frappe.get_doc(
		{
			"doctype": "Property Setter",
			"doctype_or_field": "DocField",
			"doc_type": doctype,
			"field_name": fieldname,
			"property": property_name,
			"property_type": property_type,
			"value": value,
			"name": name,
		}
	).insert(ignore_permissions=True)


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
	"""Drop fields superseded by native Project Type / HRMS department / EA cleanup."""
	for fieldname in (
		"Project-fund_project_type",
		"Expense Claim-department",
		"Employee Advance-is_emergency",
	):
		if frappe.db.exists("Custom Field", fieldname):
			frappe.delete_doc("Custom Field", fieldname, ignore_permissions=True, force=True)


def ensure_workflow_actions():
	"""Create Workflow Action Master rows used by accounting workflow fixtures.

	Fresh sites (e.g. Frappe Cloud) may not have Submit / Re-submit yet; only
	seeding Escalate left migrate failing on LinkValidationError.
	"""
	for action_name in ("Submit", "Re-submit", "Approve", "Reject", "Escalate"):
		if frappe.db.exists("Workflow Action Master", action_name):
			continue
		frappe.get_doc(
			{"doctype": "Workflow Action Master", "workflow_action_name": action_name}
		).insert(ignore_permissions=True)


def ensure_workflow_states():
	"""Create Workflow State rows used by accounting workflow fixtures."""
	defaults = (
		("Draft", "Primary", "file"),
		("Pending Approval", "Warning", "question-sign"),
		("Approved", "Success", "ok-sign"),
		("Rejected", "Danger", "remove"),
	)
	for state_name, style, icon in defaults:
		if frappe.db.exists("Workflow State", state_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Workflow State",
				"workflow_state_name": state_name,
				"style": style,
				"icon": icon,
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
	"""No accounting-specific roles remain; authority is Grade + department_head."""
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


def ensure_employee_grades():
	"""Seed the Employee Grades that carry approval / advance limits."""
	if not frappe.db.exists("DocType", "Employee Grade"):
		return
	for name in DEFAULT_GRADES:
		if frappe.db.exists("Employee Grade", name):
			continue
		try:
			frappe.get_doc({"doctype": "Employee Grade", "__newname": name}).insert(
				ignore_permissions=True
			)
		except frappe.DuplicateEntryError:
			continue


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
	if settings.get("emergency_submit_working_days") is None:
		settings.emergency_submit_working_days = 1
	if settings.get("emergency_approve_working_days") is None:
		settings.emergency_approve_working_days = 2
	if settings.get("use_grade_approval") is None:
		settings.use_grade_approval = 1
	if settings.get("use_designation_approval") is None:
		settings.use_designation_approval = 1
	if not settings.get("payout_provider"):
		settings.payout_provider = "manual"
	if not settings.get("preferred_payout_mode"):
		settings.preferred_payout_mode = "Manual"

	settings.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Volunteering Accounting Settings")


def ensure_expense_claim_payable_account():
	"""Expense Claim GL posting needs a Payable account with party support.

	Repairs companies where Default Expense Claim Payable Account points at a
	non-Payable account (e.g. Cash), which crashes approval with
	'Party Type and Party can only be set for Receivable / Payable account'.
	"""
	for company in frappe.get_all(
		"Company",
		fields=["name", "default_expense_claim_payable_account", "default_payable_account"],
	):
		current = company.default_expense_claim_payable_account
		if current and frappe.db.get_value("Account", current, "account_type") == "Payable":
			continue

		replacement = company.default_payable_account
		if not (
			replacement
			and frappe.db.get_value("Account", replacement, "account_type") == "Payable"
		):
			replacement = frappe.db.get_value(
				"Account",
				{
					"company": company.name,
					"account_type": "Payable",
					"is_group": 0,
					"disabled": 0,
				},
				"name",
			)
		if not replacement:
			continue

		frappe.db.set_value(
			"Company",
			company.name,
			"default_expense_claim_payable_account",
			replacement,
		)
		frappe.clear_cache(doctype="Company")


def ensure_designation_limits():
	"""Seed / migrate grade limits on the Approval and Advance Limits page.

	Rows used to live on Volunteering Accounting Settings; copy any orphaned
	rows over once, then upsert missing defaults. The child fieldname is still
	`designation`, but its values are Employee Grades.
	"""
	if not frappe.db.exists("DocType", "Approval and Advance Limits"):
		return

	ensure_employee_grades()
	doc = frappe.get_single("Approval and Advance Limits")

	# One-time copy of rows left behind on Volunteering Accounting Settings
	legacy_rows = frappe.get_all(
		"Designation Approval Limit",
		filters={
			"parenttype": "Volunteering Accounting Settings",
			"parentfield": "designation_limits",
		},
		fields=["name", "designation", "max_approve_amount", "max_advance_amount"],
		order_by="idx asc",
	)
	if legacy_rows and not doc.get("designation_limits"):
		for row in legacy_rows:
			doc.append(
				"designation_limits",
				{
					"designation": row.designation,
					"max_approve_amount": row.max_approve_amount,
					"max_advance_amount": row.max_advance_amount,
				},
			)
	if legacy_rows:
		frappe.db.delete(
			"Designation Approval Limit",
			{"parenttype": "Volunteering Accounting Settings"},
		)

	# Upsert missing grade limit rows from defaults (partial tables used to skip this)
	existing = {row.designation for row in (doc.get("designation_limits") or []) if row.designation}
	for grade, max_approve, max_advance in DEFAULT_GRADE_LIMITS:
		if grade in existing:
			continue
		doc.append(
			"designation_limits",
			{
				"designation": grade,
				"max_approve_amount": max_approve,
				"max_advance_amount": max_advance,
			},
		)

	# Keep Director advance headroom if an older seed left it at 25k / missing
	for row in doc.get("designation_limits") or []:
		if row.designation == "Director" and flt(row.max_advance_amount) < 50000:
			row.max_advance_amount = 50000
		if row.designation == "Director" and flt(row.max_approve_amount) < 25000:
			row.max_approve_amount = 25000

	doc.save(ignore_permissions=True)
	frappe.clear_cache(doctype="Approval and Advance Limits")
