"""Home-first project setup, scoped membership and audited financial configuration.

Legacy records remain usable until explicitly adopted in the workspace. The
new structure never creates accounting roles, project-specific approvers, or
bank accounts. Existing receipt/grade/budget/payment gates remain authoritative.
"""

import json
import math

import frappe
from frappe import _
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.permissions import add_permission, update_permission_property
from frappe.utils import cint, cstr, flt, getdate, now_datetime

from volunteering.volunteering.budget_service import CONTROL_MODES, get_budget_commitment_breakdown

PROJECT_ROLES = frozenset({"Project Proposer", "Projects User", "Projects Manager", "Project Viewer"})
SEVAMRITA_COMPANY = "Sevamrita Foundation"
BUDGET_EDITOR_ROLES = frozenset({"Projects Manager"})
FINANCE_READ_ROLES = frozenset({"Projects Manager", "Accounts Manager"})
VIEW_ALL_ROLES = frozenset({"Projects Manager", "Accounts Manager", "Project Viewer"})
FINANCE_FIELDS = frozenset(
	{
		"cost_center",
		"total_approved_budget",
		"project_budget_control",
		"account_budget_control",
		"account_budgets",
		"department_budgets",
		"estimated_costing",
		"total_costing_amount",
		"total_purchase_cost",
		"total_sales_amount",
		"total_billable_amount",
		"total_billed_amount",
		"total_consumed_material_cost",
		"gross_margin",
		"per_gross_margin",
		"budget_status",
		"project_budget_revision_reason",
	}
)
LIFECYCLE_STATES = ("Planned", "Active", "On Hold", "Completed", "Cancelled")
DETAIL_FIELDS = (
	"project_name",
	"company",
	"project_purpose",
	"project_outcomes",
	"project_owner",
	"operational_status",
	"expected_start_date",
	"expected_end_date",
	"project_type",
	"priority",
	"is_archived",
)
FINANCIAL_FIELDS = (
	"cost_center",
	"total_approved_budget",
	"project_budget_control",
	"account_budget_control",
)
INPUT_FIELDS = set(DETAIL_FIELDS + FINANCIAL_FIELDS) | {
	"participants",
	"account_budgets",
	"revision_reason",
	"financial_closed",
	"modified",
}


def setup_project_workspace():
	"""Additive schema only: no guessed owner/membership backfill or role grants."""
	create_custom_fields(
		{
			"Project": [
				{
					"fieldname": "project_proposed_by",
					"label": "Proposed By",
					"fieldtype": "Link",
					"options": "User",
					"read_only": 1,
					"insert_after": "project_name",
				},
				{
					"fieldname": "is_archived",
					"label": "Removed from active projects",
					"fieldtype": "Check",
					"default": "0",
					"read_only": 1,
					"hidden": 1,
					"insert_after": "project_proposed_by",
				},
				{
					"fieldname": "project_setup_version",
					"label": "Project Setup Version",
					"fieldtype": "Int",
					"default": "0",
					"hidden": 1,
					"read_only": 1,
					"insert_after": "project_name",
				},
				{
					"fieldname": "project_purpose",
					"label": "Purpose / Scope",
					"fieldtype": "Small Text",
					"insert_after": "project_setup_version",
				},
				{
					"fieldname": "operational_status",
					"label": "Operational Status",
					"fieldtype": "Select",
					"options": "\n" + "\n".join(LIFECYCLE_STATES),
					"insert_after": "project_purpose",
				},
				{
					"fieldname": "project_owner",
					"label": "Project Owner",
					"fieldtype": "Link",
					"options": "User",
					"insert_after": "operational_status",
				},
				{
					"fieldname": "project_participants",
					"label": "Project Participants",
					"fieldtype": "Table",
					"options": "Project Participant",
					"insert_after": "project_owner",
					"description": "Membership allows project work/claims, not financial approval or Accounts User rights.",
				},
				{
					"fieldname": "project_outcomes",
					"label": "Expected Outcomes / Deliverables",
					"fieldtype": "Small Text",
					"insert_after": "project_participants",
				},
				{
					"fieldname": "project_budget_revision_reason",
					"label": "Budget / Account Revision Reason",
					"fieldtype": "Small Text",
					"insert_after": "account_budgets",
					"description": "Required when revising a workspace project's financial configuration.",
				},
			]
		},
		update=True,
	)
	from volunteering.volunteering.accounting_setup import _ensure_property_setter

	create_custom_fields(
		{
			"File": [
				{
					"fieldname": "project_visibility",
					"label": "Project document visibility",
					"fieldtype": "Select",
					"options": "Basic\nFinancial",
					"default": "Financial",
					"read_only": 1,
					"insert_after": "is_private",
				}
			]
		},
		update=True,
	)
	for field in FINANCE_FIELDS:
		if frappe.get_meta("Project").has_field(field):
			_ensure_property_setter("Project", field, "permlevel", "2", "Int")
	for role in ("Project Proposer", "Project Viewer"):
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)
	for role in ("Project Proposer", "Projects User", "Project Viewer", "Projects Manager"):
		if not frappe.db.exists("Role", role):
			continue
		add_permission("Project", role, ptype="read")
		for permission in ("read", "create", "write", "delete", "share", "export", "report"):
			update_permission_property(
				"Project",
				role,
				0,
				permission,
				int(permission == "read" or role == "Projects Manager"),
				validate=False,
			)
	# Account allocations are not bank/ledger balances, but still finance data.
	# Desk's existing level 1 is visible to Desk User; use a separate level 2.
	frappe.db.set_value("Custom Field", "Project-account_budgets", "permlevel", 2)
	for role in FINANCE_READ_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		if not frappe.db.exists("Custom DocPerm", {"parent": "Project", "role": role, "permlevel": 2}):
			add_permission("Project", role, permlevel=2, ptype="read")
		update_permission_property("Project", role, 2, "read", 1, validate=False)
		update_permission_property(
			"Project", role, 2, "write", int(role in BUDGET_EDITOR_ROLES), validate=False
		)
	# Earlier iterations granted these general roles level-2 project fields. They
	# are intentionally revoked: only project owner, Projects Manager, Accounts
	# Manager and Administrator may see a project's financial setup.
	for role in ("System Manager", "Accounts User", "Auditor"):
		if frappe.db.exists("Custom DocPerm", {"parent": "Project", "role": role, "permlevel": 2}):
			for permission in ("read", "write", "create", "delete", "report", "export", "share"):
				update_permission_property("Project", role, 2, permission, 0, validate=False)
	frappe.clear_cache(doctype="Project")


def _logged_in():
	if frappe.session.user == "Guest":
		frappe.throw(_("Log in to open Projects."), frappe.PermissionError)


def _roles(user=None):
	return set(frappe.get_roles(user or frappe.session.user))


def _is_admin(user=None):
	# The Administrator account is the Frappe superuser. System Manager is not a
	# project-finance role and must not silently inherit project financial data.
	return (user or frappe.session.user) == "Administrator"


def can_edit_budgets(user=None):
	return _is_admin(user) or bool(_roles(user) & BUDGET_EDITOR_ROLES)


def is_project_manager(user=None):
	return can_edit_budgets(user)


def can_propose_project(user=None):
	return is_project_manager(user) or bool(_roles(user) & {"Project Proposer", "Projects User"})


def can_view_finance(doc, user=None):
	user = user or frappe.session.user
	return _is_admin(user) or bool(_roles(user) & FINANCE_READ_ROLES) or doc.get("project_owner") == user


def can_propose_changes(doc, user=None):
	user = user or frappe.session.user
	return is_project_manager(user) or user in {
		doc.owner,
		doc.get("project_owner"),
		doc.get("project_proposed_by"),
	}


def _can_oversee(user=None):
	return _is_admin(user) or bool(_roles(user) & VIEW_ALL_ROLES)


def _is_member(doc, user):
	return any(row.user == user for row in doc.get("project_participants") or [])


def _can_view(doc, user=None):
	user = user or frappe.session.user
	return (
		_can_oversee(user)
		or doc.owner == user
		or doc.get("project_proposed_by") == user
		or doc.get("project_owner") == user
		or _is_member(doc, user)
	)


def _can_edit_details(doc, user=None):
	return is_project_manager(user)


def _can_configure(doc=None):
	return can_propose_project() if doc is None else can_propose_changes(doc) and can_view_finance(doc)


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if _can_oversee(user) or not frappe.db.has_column("Project", "project_setup_version"):
		return ""
	escaped = frappe.db.escape(user)
	return f"""(`tabProject`.owner = {escaped} OR `tabProject`.project_owner = {escaped}
		OR `tabProject`.project_proposed_by = {escaped}
		OR EXISTS (SELECT 1 FROM `tabProject Participant` participant
			WHERE participant.parent = `tabProject`.name AND participant.parenttype = 'Project'
			AND participant.parentfield = 'project_participants' AND participant.user = {escaped}))"""


def has_permission(doc, user=None, ptype=None, **kwargs):
	user = user or frappe.session.user
	if ptype == "create" or doc.is_new():
		return is_project_manager(user)
	if not _can_view(doc, user):
		return False
	if ptype in ("write", "delete", "share") and not _can_edit_details(doc, user):
		return False
	return True


def _share_member(doc, user):
	return user and (_can_view(doc, user))


def validate_project_share(share, method=None):
	"""DocShare otherwise overrides controller denials and list conditions."""
	if share.share_doctype != "Project":
		from volunteering.volunteering.project_proposals import validate_request_share

		validate_request_share(share)
		return
	doc = frappe.get_doc("Project", share.share_name)
	if not cint(doc.get("project_setup_version")):
		return
	if cint(share.everyone) or not _share_member(doc, share.user):
		frappe.throw(
			_("Add the user as a project participant instead of sharing outside membership."),
			frappe.PermissionError,
		)
	if (cint(share.write) or cint(share.share) or cint(share.submit)) and not _can_edit_details(
		doc, share.user
	):
		frappe.throw(
			_("Project participants may receive read-only shares, not project editing authority."),
			frappe.PermissionError,
		)


def _validate_existing_shares(doc):
	conflicts = []
	for share in frappe.get_all(
		"DocShare",
		filters={"share_doctype": "Project", "share_name": doc.name},
		fields=["user", "everyone", "write", "share", "submit"],
	):
		if (
			cint(share.everyone)
			or not _share_member(doc, share.user)
			or (
				(cint(share.write) or cint(share.share) or cint(share.submit))
				and not _can_edit_details(doc, share.user)
			)
		):
			conflicts.append(share.user or "Everyone")
	if conflicts:
		frappe.throw(
			_(
				"Review and remove existing Project shares outside the selected membership/editing rights before saving: {0}. No shares have been changed."
			).format(", ".join(conflicts))
		)


def _validate_staff_user(user):
	values = frappe.db.get_value("User", user, ["enabled", "user_type", "full_name"], as_dict=True)
	if not values or not values.enabled or values.user_type != "System User":
		frappe.throw(_("{0} must be an enabled staff (System User) account.").format(user))
	return values.full_name or user


def _budget_values(doc):
	return {
		**{
			field: (flt(doc.get(field)) if field == "total_approved_budget" else doc.get(field) or "")
			for field in FINANCIAL_FIELDS
		},
		"account_budgets": sorted(
			[
				{
					"budget_key": row.budget_key or "",
					"employee_label": row.employee_label or "",
					"approved_amount": flt(row.approved_amount),
					"is_active": cint(row.is_active),
				}
				for row in doc.get("account_budgets") or []
			],
			key=lambda row: row["budget_key"],
		),
		"financial_closed": doc.get("budget_status") == "Closed",
	}


def _closure_blockers(project):
	blockers = []
	for doctype, extra in (
		("Expense Claim", {"status": ["not in", ["Paid", "Rejected", "Cancelled"]]}),
		("Purchase Order", {"status": ["not in", ["Completed", "Closed", "Cancelled"]]}),
		("Purchase Invoice", {"outstanding_amount": [">", 0]}),
	):
		filters = {"project": project, "docstatus": ["!=", 2], **extra}
		if frappe.db.has_column(doctype, "workflow_state"):
			filters["workflow_state"] = ["!=", "Rejected"]
		for name in frappe.get_all(doctype, filters=filters, pluck="name", limit_page_length=5):
			blockers.append(f"{doctype}: {name}")
	return blockers


def validate_project_structure(doc, method=None, validation_only=False):
	previous = doc.get_doc_before_save()
	from volunteering.volunteering.project_proposals import approved_application_allowed, project_values

	if not validation_only:
		changed = previous and (
			project_values(previous) != project_values(doc)
			or any(
				doc.get(field) != previous.get(field)
				for field in (
					"status",
					"is_active",
					"department",
					"project_proposed_by",
					"project_setup_version",
				)
			)
		)
		if (
			changed or (doc.is_new() and cint(doc.get("project_setup_version")))
		) and not approved_application_allowed(doc):
			frappe.throw(
				_(
					"Create a proposal in Home → Projects. Project configuration changes require a Projects Manager's approval."
				),
				frappe.PermissionError,
			)
	if previous and cint(previous.get("project_setup_version")):
		if cint(doc.get("project_setup_version")) != 1:
			frappe.throw(_("A workspace project cannot be changed back to legacy setup."))
	if not cint(doc.get("project_setup_version")):
		return  # Preserve legacy projects until explicitly adopted with real people.
	doc.project_setup_version = 1
	if not cstr(doc.get("project_purpose")).strip() or not doc.get("project_owner") or not doc.get("company"):
		frappe.throw(_("Project Company, Purpose / Scope and one Project Owner are required."))
	_validate_staff_user(doc.project_owner)
	participants = doc.get("project_participants") or []
	if not participants:
		frappe.throw(_("Select at least one project participant; the owner may also be a participant."))
	seen = set()
	for row in participants:
		if row.user in seen:
			frappe.throw(_("Project participant {0} appears more than once.").format(row.user))
		seen.add(row.user)
		row.full_name = _validate_staff_user(row.user)
		# All participant membership is deliberately basic. Financial access comes
		# only from project ownership or the company-wide manager roles.
		row.access_level = "Basic"
	if previous:
		_validate_existing_shares(doc)
	if doc.operational_status not in LIFECYCLE_STATES:
		frappe.throw(_("Choose a valid Operational Status."))
	if (
		doc.expected_start_date
		and doc.expected_end_date
		and getdate(doc.expected_end_date) < getdate(doc.expected_start_date)
	):
		frappe.throw(_("Project end date cannot be before its start date."))
	cost_center = (
		frappe.db.get_value("Cost Center", doc.get("cost_center"), ["company", "is_group"], as_dict=True)
		if doc.get("cost_center")
		else None
	)
	if not cost_center or cost_center.company != doc.company or cost_center.is_group:
		frappe.throw(_("Choose a non-group Cost Centre belonging to the Project's Company."))
	for amount in [doc.get("total_approved_budget"), *(row.approved_amount for row in doc.account_budgets)]:
		if not math.isfinite(flt(amount)) or flt(amount) < 0:
			frappe.throw(_("Budget amounts must be finite and non-negative."))
	if previous and previous.company and previous.company != doc.company:
		frappe.throw(_("Company cannot be changed after creation; create a separate project instead."))
	before = _budget_values(previous) if previous else {}
	after = _budget_values(doc)
	if validation_only:
		return
	if before != after:
		if previous:
			if not can_edit_budgets():
				frappe.throw(
					_(
						"Only Projects Manager or System Manager may approve budget and permitted-account revisions."
					),
					frappe.PermissionError,
				)
			reason = cstr(doc.get("project_budget_revision_reason")).strip()
			if not reason:
				frappe.throw(_("Enter a reason for the budget / permitted-account revision."))
		else:
			if not frappe.has_permission("Project", "create"):
				frappe.throw(_("You do not have permission to create Projects."), frappe.PermissionError)
			reason = _("Initial project setup")
		if after["financial_closed"] != before.get("financial_closed", False):
			if not is_project_manager():
				frappe.throw(
					_("Only Projects Manager or System Manager may financially close or reopen a project."),
					frappe.PermissionError,
				)
			if after["financial_closed"] and previous and (blockers := _closure_blockers(doc.name)):
				frappe.throw(
					_("Settle or close outstanding documents first: {0}").format(", ".join(blockers))
				)
		doc.flags.project_budget_revision = {"before": before, "after": after, "reason": reason}
	doc.project_budget_revision_reason = ""
	doc.status = doc.operational_status if doc.operational_status in ("Completed", "Cancelled") else "Open"
	doc.is_active = "Yes" if doc.operational_status in ("Active", "Planned") else "No"
	doc.flags.ignore_version = False


def record_budget_revision(doc, method=None):
	change = doc.flags.pop("project_budget_revision", None)
	if not change:
		return
	revision = frappe.get_doc(
		{
			"doctype": "Project Budget Revision",
			"project": doc.name,
			"changed_by": frappe.session.user,
			"changed_on": now_datetime(),
			"reason": change["reason"],
			"before_values": json.dumps(change["before"], sort_keys=True),
			"after_values": json.dumps(change["after"], sort_keys=True),
		}
	)
	revision.flags.from_project_workspace = True
	revision.insert(ignore_permissions=True)


def validate_project_claim_access(doc, method=None):
	if not doc.get("project"):
		return
	project = frappe.get_doc("Project", doc.project)
	if not cint(project.get("project_setup_version")):
		return
	previous = doc.get_doc_before_save()
	# Lifecycle/membership limits apply when an employee raises/resubmits spend,
	# not when finance settles a previously accepted claim on a completed project.
	if (
		previous
		and previous.project == doc.project
		and previous.get("workflow_state")
		not in (None, "Draft", "Receipt Correction Required", "Rejected", "")
	):
		return
	user = (
		frappe.db.get_value("Employee", doc.get("employee"), "user_id")
		if doc.doctype == "Expense Claim"
		else doc.owner
	)
	if not user or not _is_member(project, user):
		frappe.throw(
			_("The claimant must be a listed project member. Every project member can submit bills."),
			frappe.PermissionError,
		)
	if project.operational_status != "Active":
		frappe.throw(
			_("New claims require an Active project; this project is {0}.").format(project.operational_status)
		)
	if project.budget_status == "Closed":
		frappe.throw(_("This project is financially closed."))


def _capabilities(doc=None):
	return {
		"current_user": frappe.session.user,
		"can_create": can_propose_project(),
		"can_manage": is_project_manager(),
		"can_propose_changes": bool(doc and can_propose_changes(doc)),
		"can_view_financials": bool(doc and can_view_finance(doc)),
		"can_edit_details": False,
		"can_edit_budgets": can_edit_budgets(),
		"can_configure": _can_configure(doc),
		"can_close_financially": bool(doc and can_propose_changes(doc) and can_view_finance(doc)),
	}


def _serialize(doc):
	capabilities = _capabilities(doc)
	can_read_finance = can_view_finance(doc)
	financial_status = get_budget_commitment_breakdown(doc.name) if can_read_finance else None
	suggested_keys = {
		row.budget_key for row in doc.get("expense_account_mappings") or [] if row.expense_account
	}
	result = {
		"name": doc.name,
		"modified": str(doc.modified),
		"legacy": not cint(doc.get("project_setup_version")),
		"mapping_ready": all(
			row.budget_key in suggested_keys for row in doc.get("account_budgets") or [] if cint(row.is_active)
		),
		"can_map_accounts": frappe.session.user == "Administrator" or "Accounts Manager" in _roles(),
		**{field: doc.get(field) or "" for field in DETAIL_FIELDS},
		**(
			{
				**{field: doc.get(field) or "" for field in FINANCIAL_FIELDS},
				"financial_closed": doc.get("budget_status") == "Closed",
				"budget_status": doc.get("budget_status"),
				"committed": financial_status["total_committed"],
				"financial_status": financial_status,
			}
			if can_read_finance
			else {}
		),
		"participants": [row.user for row in doc.get("project_participants") or []],
		"members": [
			{"user": row.user, "full_name": row.full_name} for row in doc.get("project_participants") or []
		],
		"permitted_accounts": [
			{
				"budget_key": row.budget_key,
				"employee_label": row.employee_label,
				"mapped": row.budget_key in suggested_keys,
			}
			for row in doc.get("account_budgets") or []
			if cint(row.is_active)
		],
		**(
			{
				"account_budgets": [
					{
						"budget_key": row.budget_key,
						"employee_label": row.employee_label,
						"is_active": cint(row.is_active),
						**({"approved_amount": flt(row.approved_amount)} if can_read_finance else {}),
					}
					for row in doc.get("account_budgets") or []
				]
			}
			if can_read_finance
			else {}
		),
		"capabilities": capabilities,
	}
	if not result["operational_status"]:
		result["operational_status"] = (
			doc.status
			if doc.status in ("Completed", "Cancelled")
			else "Active"
			if doc.is_active == "Yes"
			else "On Hold"
		)
	from volunteering.volunteering.project_documents import list_documents

	result["attachments"] = list_documents("Project", doc.name)
	result["revisions"] = []
	if can_read_finance:
		result["revisions"] = frappe.get_all(
			"Project Budget Revision",
			filters={"project": doc.name},
			fields=["changed_by", "changed_on", "reason", "before_values", "after_values"],
			order_by="creation desc",
			limit_page_length=20,
		)
	return result


@frappe.whitelist()
def get_projects(include_removed=False):
	_logged_in()
	rows = frappe.get_list(
		"Project",
		filters={} if cint(include_removed) and is_project_manager() else {"is_archived": 0},
		fields=[
			"name",
			"project_name",
			"status",
			"company",
			"project_owner",
			"operational_status",
			"project_setup_version",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=100,
	)
	return {"projects": rows, "capabilities": _capabilities()}


@frappe.whitelist()
def get_project(project):
	_logged_in()
	doc = frappe.get_doc("Project", project)
	if not _can_view(doc):
		frappe.throw(_("You are not a participant of this project."), frappe.PermissionError)
	doc.check_permission("read")
	return _serialize(doc)


@frappe.whitelist()
def get_setup_options(project=None):
	_logged_in()
	doc = frappe.get_doc("Project", project) if project else None
	if doc:
		get_project(project)  # The editor must also be allowed to view this record.
	if not _can_configure(doc) and not (doc and can_propose_changes(doc)):
		frappe.throw(
			_("Project setup options are only available to authorised project editors."),
			frappe.PermissionError,
		)
	# Only identifiers/labels needed for setup, never bank details or balances.
	users = frappe.get_all(
		"User",
		filters={"enabled": 1, "user_type": "System User", "name": ["not in", ["Guest"]]},
		fields=["name", "full_name"],
		order_by="full_name asc",
		limit_page_length=500,
	)
	project_managers = frappe.get_all(
		"Has Role",
		filters={"role": "Projects Manager", "parenttype": "User"},
		fields=["parent as name"],
		limit_page_length=0,
	)
	manager_names = sorted({row.name for row in project_managers})
	manager_details = {
		row.name: row
		for row in frappe.get_all(
			"User",
			filters={
				"enabled": 1,
				"user_type": "System User",
				"name": ["in", manager_names or [""]],
			},
			fields=["name", "full_name"],
			limit_page_length=0,
		)
	}
	expense_labels = frappe.db.sql_list(
		"""SELECT DISTINCT TRIM(b.employee_label)
		FROM `tabProject Account Budget` b
		JOIN `tabProject` p ON p.name=b.parent AND b.parenttype='Project'
		WHERE p.project_setup_version > 0
			AND TRIM(COALESCE(b.employee_label, '')) != ''
			AND LOWER(TRIM(b.employee_label)) != 'others'
		ORDER BY TRIM(b.employee_label)"""
	)
	companies = frappe.get_list(
		"Company", filters={"name": SEVAMRITA_COMPANY}, fields=["name", "default_currency"]
	)
	if not companies:
		frappe.throw(
			_("Sevamrita Foundation must be configured and accessible before creating projects."),
			frappe.PermissionError,
		)
	company_names = [row.name for row in companies]
	return {
		"current_user": frappe.session.user,
		"default_company": SEVAMRITA_COMPANY,
		"users": users,
		"project_managers": sorted(
			(manager_details[name] for name in manager_names if name in manager_details),
			key=lambda row: ((row.full_name or "").casefold(), row.name.casefold()),
		),
		"expense_breakup_labels": expense_labels,
		"companies": companies,
		"control_modes": CONTROL_MODES,
		"lifecycle_states": LIFECYCLE_STATES,
		"project_types": frappe.get_all("Project Type", pluck="name", order_by="name asc"),
		"cost_centres": frappe.get_all(
			"Cost Center",
			filters={"is_group": 0, "company": ["in", company_names]},
			fields=["name", "company"],
			limit_page_length=500,
		)
		if _can_configure(doc)
		else [],
	}


@frappe.whitelist(methods=["POST"])
def save_project(data, project=None):
	frappe.throw(
		_("Direct project saving is disabled. Save and submit a project proposal from Home → Projects."),
		frappe.PermissionError,
	)


def _save_approved_project(data, project=None, proposed_by=None):
	_logged_in()
	data = frappe.parse_json(data)
	if not isinstance(data, dict) or set(data) - INPUT_FIELDS:
		frappe.throw(_("Invalid project form fields."))
	if project:
		doc = frappe.get_doc("Project", project)
		if not _can_view(doc) or not (_can_edit_details(doc) or can_edit_budgets()):
			frappe.throw(_("You cannot edit this project."), frappe.PermissionError)
		if not data.get("modified") or str(doc.modified) != data["modified"]:
			frappe.throw(
				_("This project changed since you opened it. Reload before saving."),
				frappe.TimestampMismatchError,
			)
	else:
		if not frappe.has_permission("Project", "create"):
			frappe.throw(_("You do not have permission to create Projects."), frappe.PermissionError)
		doc = frappe.new_doc("Project")
	from volunteering.volunteering.project_proposals import approved_application_allowed

	if not approved_application_allowed(doc):
		frappe.throw(_("A manager-approved project request is required."), frappe.PermissionError)
	if not project:
		doc.project_proposed_by = proposed_by
	# Home is Sevamrita's workspace; company is an accounting dependency, not a user choice.
	if data.get("company") and data["company"] != SEVAMRITA_COMPANY:
		frappe.throw(_("Projects in this workspace belong to Sevamrita Foundation."))
	if not project or not doc.company:
		if not frappe.has_permission("Company", "read", doc=SEVAMRITA_COMPANY):
			frappe.throw(_("You cannot create a project for Sevamrita Foundation."), frappe.PermissionError)
		doc.company = SEVAMRITA_COMPANY
	for field in DETAIL_FIELDS + FINANCIAL_FIELDS:
		if field in data and field != "company":
			doc.set(field, data[field])
	if "participants" in data:
		if not isinstance(data["participants"], list) or len(data["participants"]) > 100:
			frappe.throw(_("Select at most 100 participants."))
		doc.set(
			"project_participants",
			[
				{"user": row, "access_level": "Basic"}
				if isinstance(row, str)
				else {"user": row.get("user"), "access_level": "Basic"}
				for row in data["participants"]
			],
		)
	if "account_budgets" in data:
		if not isinstance(data["account_budgets"], list) or len(data["account_budgets"]) > 100:
			frappe.throw(_("Select at most 100 expense labels."))
		rows = []
		for row in data["account_budgets"]:
			if not isinstance(row, dict) or set(row) - {
				"budget_key",
				"employee_label",
				"approved_amount",
				"is_active",
			}:
				frappe.throw(_("Invalid expense-label fields."))
			rows.append(dict(row))
		from volunteering.volunteering.project_account_mapping import resolve_budget_rows

		doc.set("account_budgets", resolve_budget_rows(doc, rows))
	doc.project_setup_version = 1
	doc.project_budget_revision_reason = cstr(data.get("revision_reason")).strip()
	if "financial_closed" in data:
		doc.budget_status = "Closed" if cint(data["financial_closed"]) else "Active"
	# The request, manager authority, baseline and fields were checked above and
	# are rechecked by document hooks. No client receives a direct-save bypass.
	doc.save(ignore_permissions=True)
	return _serialize(doc)


@frappe.whitelist(methods=["POST"])
def upload_project_document(project, filename, content):
	frappe.throw(
		_("Attach supporting documents to a project proposal so additions are reviewed before publication."),
		frappe.PermissionError,
	)


def validate_project_deletion(doc, method=None):
	frappe.throw(
		_(
			"Project history is retained. Projects Managers can remove unused projects from Home → Projects instead."
		),
		frappe.PermissionError,
	)


def has_financial_records(project):
	for doctype in ("Expense Claim", "Employee Advance", "Purchase Order", "Purchase Invoice", "GL Entry"):
		if frappe.db.has_column(doctype, "project") and frappe.db.exists(doctype, {"project": project}):
			return True
	for doctype in ("Purchase Order Item", "Purchase Invoice Item"):
		if frappe.db.exists(doctype, {"project": project}):
			return True
	return False
