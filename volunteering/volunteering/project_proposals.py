"""Transactional project proposals: no effective changes before one manager approves."""

import json
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.utils import cint, cstr, now_datetime

from volunteering.volunteering import project_workspace as workspace

_mutation = ContextVar("project_request_mutation", default=False)
_application = ContextVar("approved_project_application", default=None)
EDITABLE = {"Draft", "Correction Required"}
OTHERS_LABEL = "Others"
REQUEST_FIELDS = set(workspace.DETAIL_FIELDS + workspace.FINANCIAL_FIELDS) | {
	"participants",
	"account_budgets",
	"financial_closed",
}


@contextmanager
def mutation():
	token = _mutation.set(True)
	try:
		yield
	finally:
		_mutation.reset(token)


def approved_application_allowed(doc):
	context = _application.get()
	return bool(
		context and workspace.is_project_manager() and context[0] == (None if doc.is_new() else doc.name)
	)


def validate_request_mutation(doc):
	if not _mutation.get():
		frappe.throw(
			_("Use the Home proposal workflow; request content and decisions cannot be edited directly."),
			frappe.PermissionError,
		)


def project_values(doc):
	return {
		**{field: doc.get(field) or "" for field in workspace.DETAIL_FIELDS + workspace.FINANCIAL_FIELDS},
		"participants": [
			{"user": row.user, "access_level": row.get("access_level") or "Basic"}
			for row in doc.get("project_participants") or []
		],
		"account_budgets": [
			{
				"budget_key": row.budget_key or "",
				"employee_label": row.employee_label or "",
				"approved_amount": row.approved_amount or 0,
				"is_active": cint(row.is_active),
			}
			for row in doc.get("account_budgets") or []
		],
		"financial_closed": doc.get("budget_status") == "Closed",
	}


def _readable(doc, user=None):
	return workspace.is_project_manager(user) or doc.proposed_by == (user or frappe.session.user)


def _is_assigned_manager(doc, user=None):
	user = user or frappe.session.user
	return bool(
		doc.assigned_approver and doc.assigned_approver == user and workspace.is_project_manager(user)
	)


def _validate_assigned_approver(user):
	user = cstr(user).strip()
	if not user:
		frappe.throw(_("Choose the Projects Manager who should review this proposal."))
	values = frappe.db.get_value("User", user, ["enabled", "user_type"], as_dict=True)
	if (
		not values
		or not values.enabled
		or values.user_type != "System User"
		or not workspace.is_project_manager(user)
	):
		frappe.throw(_("The assigned reviewer must be an enabled Projects Manager."))
	return user


def has_permission(doc, user=None, ptype=None, **kwargs):
	return ptype in ("read", "select", "print", "report") and _readable(doc, user)


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	return (
		""
		if workspace.is_project_manager(user)
		else f"`tabProject Proposal`.proposed_by = {frappe.db.escape(user)}"
	)


def _load(name, modified=None, lock=False):
	workspace._logged_in()
	doc = frappe.get_doc("Project Proposal", name)
	if not _readable(doc):
		frappe.throw(_("You cannot access this project request."), frappe.PermissionError)
	if lock:
		frappe.db.sql("SELECT name FROM `tabProject Proposal` WHERE name=%s FOR UPDATE", name)
		doc.reload()
	if modified is not None and str(doc.modified) != modified:
		frappe.throw(
			_("This request changed. Reload before saving or deciding."), frappe.TimestampMismatchError
		)
	return doc


def _project(project):
	doc = frappe.get_doc("Project", project)
	if not workspace._can_view(doc) or not workspace.can_propose_changes(doc):
		frappe.throw(
			_("Only a project proposer, owner or authorized manager may request changes."),
			frappe.PermissionError,
		)
	return doc


def _data(data, project=None):
	data = frappe.parse_json(data)
	if not isinstance(data, dict) or set(data) - REQUEST_FIELDS:
		frappe.throw(_("Invalid project request fields."))
	data = json.loads(json.dumps(data))
	data.pop("company", None)
	if (
		project
		and not workspace.can_view_finance(project)
		and set(data) & (set(workspace.FINANCIAL_FIELDS) | {"account_budgets", "financial_closed"})
	):
		frappe.throw(
			_("Financial visibility is required to propose financial changes."), frappe.PermissionError
		)
	if "participants" in data:
		if not isinstance(data["participants"], list) or len(data["participants"]) > 100:
			frappe.throw(_("Select at most 100 members."))
		members = []
		for row in data["participants"]:
			row = {"user": row, "access_level": "Basic"} if isinstance(row, str) else row
			if not isinstance(row, dict) or set(row) - {"user", "access_level"}:
				frappe.throw(_("Invalid project membership."))
			workspace._validate_staff_user(row.get("user"))
			members.append({"user": row["user"], "access_level": "Basic"})
		data["participants"] = members
	if "account_budgets" in data:
		if not isinstance(data["account_budgets"], list) or len(data["account_budgets"]) > 100:
			frappe.throw(_("Select at most 100 expense labels."))
		for row in data["account_budgets"]:
			if not isinstance(row, dict) or set(row) - {
				"budget_key",
				"employee_label",
				"approved_amount",
				"is_active",
			}:
				frappe.throw(_("Project proposals contain expense labels and budgets, not ledger accounts."))
			if not row.get("budget_key"):
				row["budget_key"] = frappe.generate_hash(length=20)
			elif frappe.db.exists(
				"Project Account Budget",
				{
					"budget_key": row["budget_key"],
					"parent": ["!=", project.name if project else ""],
				},
			):
				frappe.throw(_("This expense label belongs to another project."))
	if "is_archived" in data and not workspace.is_project_manager():
		frappe.throw(
			_("Only Projects Managers can remove or restore unused projects."), frappe.PermissionError
		)
	if project and cint(data.get("is_archived")) and workspace.has_financial_records(project.name):
		frappe.throw(
			_(
				"This project has financial records and cannot be deleted. Propose operational completion or cancellation instead."
			)
		)
	return data


def _amount(value, label):
	try:
		amount = Decimal(str(value or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	except InvalidOperation, ValueError:
		frappe.throw(_("{0} must be a valid amount.").format(label))
	if not amount.is_finite() or amount < 0:
		frappe.throw(_("{0} must be a finite, non-negative amount.").format(label))
	return amount


def _normalise_expense_breakup(project):
	"""Make the approved breakup equal the project ceiling, with a server-owned Others row."""
	total = _amount(project.get("total_approved_budget"), _("Total approved budget"))
	others = []
	allocated = Decimal("0")
	for row in project.get("account_budgets") or []:
		label = " ".join(cstr(row.get("employee_label")).split())
		if label.casefold() == OTHERS_LABEL.casefold():
			others.append(row)
			continue
		allocated += _amount(row.get("approved_amount"), label or _("Expense breakup amount"))
	if allocated > total:
		frappe.throw(
			_("Expense break up exceeds the total project budget by {0}.").format(
				frappe.format_value(float(allocated - total), {"fieldtype": "Currency"})
			)
		)
	remainder = total - allocated
	primary = others[0] if others else None
	if primary is None and remainder > 0:
		primary = project.append(
			"account_budgets",
			{
				"budget_key": frappe.generate_hash(length=20),
				"employee_label": OTHERS_LABEL,
			},
		)
	if primary:
		primary.employee_label = OTHERS_LABEL
		primary.approved_amount = float(remainder)
		primary.is_active = int(remainder > 0)
	for duplicate in others[1:]:
		project.remove(duplicate)
	return project


def _event(doc, action, comment="", before=None, after=None):
	doc.append(
		"events",
		{
			"action": action,
			"actor": frappe.session.user,
			"acted_on": now_datetime(),
			"comment": comment,
			"before_data": json.dumps(before or {}, sort_keys=True),
			"after_data": json.dumps(after or {}, sort_keys=True),
		},
	)


def _store(doc):
	with mutation():
		doc.save(ignore_permissions=True)
	return _serialize(doc)


def backfill_unassigned_project_proposals():
	"""Return legacy pending requests so their proposer can assign a manager.

	Older databases may contain pending proposals created before the assigned
	reviewer field existed. Leaving them pending would make them impossible to
	decide under the new assigned-manager rule. This migration is idempotent and
	keeps the transition in the proposal's audit history.
	"""
	if not frappe.db.table_exists("Project Proposal") or not frappe.db.has_column(
		"Project Proposal", "assigned_approver"
	):
		return
	for name in frappe.db.sql_list(
		"""SELECT name FROM `tabProject Proposal`
		WHERE proposal_status='Pending Approval'
			AND TRIM(COALESCE(assigned_approver, ''))=''"""
	):
		doc = frappe.get_doc("Project Proposal", name)
		doc.proposal_status = "Correction Required"
		_event(
			doc,
			"Returned for manager assignment",
			"Choose a Projects Manager and resubmit this legacy request.",
		)
		with mutation():
			doc.save(ignore_permissions=True)


def _redact(data, finance):
	return (
		data
		if finance
		else {
			key: value
			for key, value in data.items()
			if key not in workspace.FINANCE_FIELDS and key != "financial_closed"
		}
	)


def _serialize(doc):
	project = frappe.get_doc("Project", doc.project) if doc.project else None
	finance = (
		workspace.is_project_manager()
		or doc.request_kind == "New Project"
		or bool(project and workspace.can_view_finance(project))
	)
	data = _redact(json.loads(doc.proposal_data or "{}"), finance)
	current = _redact(project_values(project), workspace.can_view_finance(project)) if project else {}
	return {
		"name": doc.name,
		"modified": str(doc.modified),
		"title": doc.title,
		"request_kind": doc.request_kind,
		"project": doc.project,
		"proposed_by": doc.proposed_by,
		"assigned_approver": doc.assigned_approver,
		"proposal_status": doc.proposal_status,
		"request_reason": doc.request_reason or "",
		"base_modified": doc.base_modified,
		"data": data,
		"current": current,
		"stale": bool(
			project and doc.request_kind == "Project Change" and str(project.modified) != doc.base_modified
		),
		"decided_by": doc.decided_by,
		"decided_on": doc.decided_on,
		"can_edit": (doc.proposal_status in EDITABLE and doc.proposed_by == frappe.session.user)
		or (_is_assigned_manager(doc) and doc.proposal_status == "Pending Approval"),
		"can_submit": doc.proposal_status in EDITABLE and doc.proposed_by == frappe.session.user,
		"can_withdraw": doc.proposal_status in EDITABLE and doc.proposed_by == frappe.session.user,
		"can_review": _is_assigned_manager(doc) and doc.proposal_status == "Pending Approval",
		"can_view_financials": finance,
		"events": [
			{
				"action": row.action,
				"actor": row.actor,
				"acted_on": row.acted_on,
				"comment": row.comment,
				"before": _redact(json.loads(row.before_data or "{}"), finance),
				"after": _redact(json.loads(row.after_data or "{}"), finance),
			}
			for row in doc.events
		],
		"attachments": __import__(
			"volunteering.volunteering.project_documents", fromlist=["list_documents"]
		).list_documents("Project Proposal", doc.name),
	}


@frappe.whitelist()
def get_proposal(proposal):
	return _serialize(_load(proposal))


@frappe.whitelist()
def get_proposals():
	workspace._logged_in()
	filters = {} if workspace.is_project_manager() else {"proposed_by": frappe.session.user}
	return frappe.get_all(
		"Project Proposal",
		filters=filters,
		fields=[
			"name",
			"title",
			"request_kind",
			"project",
			"proposed_by",
			"assigned_approver",
			"proposal_status",
			"modified",
		],
		order_by="modified desc",
		limit_page_length=100,
	)


@frappe.whitelist(methods=["POST"])
def save_proposal(data, proposal=None, project=None, modified=None, reason="", assigned_approver=None):
	workspace._logged_in()
	doc = _load(proposal, modified, lock=True) if proposal else None
	if doc:
		if not modified:
			frappe.throw(_("Reload the request before saving."), frappe.TimestampMismatchError)
		if doc.proposal_status not in EDITABLE and not (
			_is_assigned_manager(doc) and doc.proposal_status == "Pending Approval"
		):
			frappe.throw(
				_("Submitted requests are locked until returned for correction."), frappe.PermissionError
			)
		if doc.proposal_status in EDITABLE and doc.proposed_by != frappe.session.user:
			frappe.throw(_("Only the proposer may edit a draft or returned request."), frappe.PermissionError)
		project = doc.project if doc.request_kind == "Project Change" else None
	project_doc = _project(project) if project else None
	if not doc and not project and not workspace.can_propose_project():
		frappe.throw(_("Project Proposer or Projects Manager is required."), frappe.PermissionError)
	if not frappe.has_permission("Company", "read", doc=workspace.SEVAMRITA_COMPANY):
		frappe.throw(_("Sevamrita Foundation is not accessible."), frappe.PermissionError)
	patch = _data(data, project_doc)
	before = json.loads(doc.proposal_data or "{}") if doc else {}
	# Basic owners cannot replace a manager's hidden financial amendment when a request is returned.
	if project_doc and not workspace.can_view_finance(project_doc):
		patch = {
			**{
				key: value
				for key, value in before.items()
				if key in workspace.FINANCE_FIELDS or key in ("financial_closed", "account_budgets")
			},
			**patch,
		}
	if not doc:
		doc = frappe.new_doc("Project Proposal")
		doc.update(
			{
				"request_kind": "Project Change" if project else "New Project",
				"project": project,
				"proposed_by": frappe.session.user,
				"proposal_status": "Draft",
			}
		)
		# A planning draft may be saved before the proposer knows who should
		# review it. Submission remains strict in ``submit_proposal``.
		doc.assigned_approver = (
			_validate_assigned_approver(assigned_approver) if cstr(assigned_approver).strip() else None
		)
	elif assigned_approver and assigned_approver != doc.assigned_approver:
		if doc.proposed_by != frappe.session.user or doc.proposal_status not in EDITABLE:
			frappe.throw(
				_("Only the proposer may change the assigned manager before submission."),
				frappe.PermissionError,
			)
		doc.assigned_approver = _validate_assigned_approver(assigned_approver)
	if project_doc and doc.proposal_status in EDITABLE:
		doc.base_modified = str(project_doc.modified)
	doc.proposal_data = json.dumps(patch, sort_keys=True)
	doc.title = patch.get("project_name") or (
		project_doc.project_name if project_doc else "Untitled project proposal"
	)
	doc.request_reason = cstr(reason).strip()
	_event(
		doc,
		"Manager edited request"
		if workspace.is_project_manager() and doc.proposal_status == "Pending Approval"
		else "Draft saved",
		doc.request_reason,
		before,
		patch,
	)
	return _store(doc)


@frappe.whitelist(methods=["POST"])
def submit_proposal(proposal, modified):
	doc = _load(proposal, modified, lock=True)
	if doc.proposal_status not in EDITABLE:
		frappe.throw(_("Only draft or returned requests may be submitted."))
	if doc.proposed_by != frappe.session.user:
		frappe.throw(_("Only the proposer may submit this request."), frappe.PermissionError)
	doc.assigned_approver = _validate_assigned_approver(doc.assigned_approver)
	if doc.request_kind == "New Project" and not workspace.can_propose_project():
		frappe.throw(_("Project proposal authority is required."), frappe.PermissionError)
	if doc.request_kind == "Project Change":
		project = _project(doc.project)
		if str(project.modified) != doc.base_modified:
			frappe.throw(
				_("The approved project changed. Reload and save your draft against the latest details."),
				frappe.TimestampMismatchError,
			)
		if not doc.request_reason:
			frappe.throw(_("Explain why these project changes are requested."))
		frappe.db.sql("SELECT name FROM `tabProject` WHERE name=%s FOR UPDATE", doc.project)
		if frappe.db.exists(
			"Project Proposal",
			{"project": doc.project, "proposal_status": "Pending Approval", "name": ["!=", doc.name]},
		):
			frappe.throw(_("Another change request is awaiting approval for this project."))
	# Semantic validation runs without saving a Project or generating a revision.
	_validate_candidate(doc)
	doc.proposal_status = "Pending Approval"
	_event(doc, "Submitted for approval", doc.request_reason)
	return _store(doc)


def _candidate(doc):
	project = (
		frappe.get_doc("Project", doc.project)
		if doc.request_kind == "Project Change"
		else frappe.new_doc("Project")
	)
	data = json.loads(doc.proposal_data or "{}")
	project.company = project.company or workspace.SEVAMRITA_COMPANY
	for field in workspace.DETAIL_FIELDS + workspace.FINANCIAL_FIELDS:
		if field in data and field != "company":
			project.set(field, data[field])
	if "participants" in data:
		project.set("project_participants", data["participants"])
	if "account_budgets" in data:
		from volunteering.volunteering.project_account_mapping import resolve_budget_rows

		project.set("account_budgets", resolve_budget_rows(project, data["account_budgets"]))
	if "financial_closed" in data:
		project.budget_status = "Closed" if cint(data["financial_closed"]) else "Active"
	project.project_setup_version = 1
	return project


def _validate_candidate(doc):
	from volunteering.volunteering.budget_service import validate_project_department_budgets

	project = _candidate(doc)
	if not cstr(project.get("project_name")).strip():
		frappe.throw(_("Enter a Project Name before submitting this proposal."))
	_normalise_expense_breakup(project)
	# Validation only: bypass approval enforcement through a distinct validator parameter,
	# never a client-supplied Document flag. Permission/decision checks are not performed here.
	validate_project_department_budgets(project)
	workspace.validate_project_structure(project, validation_only=True)
	return project


@frappe.whitelist(methods=["POST"])
def review_proposal(proposal, action, modified, comments="", data=None):
	workspace._logged_in()
	doc = _load(proposal, modified, lock=True)
	if not _is_assigned_manager(doc):
		frappe.throw(
			_("Only the Projects Manager assigned by the proposer may decide this request."),
			frappe.PermissionError,
		)
	if doc.proposal_status != "Pending Approval":
		frappe.throw(_("This request is no longer awaiting approval."))
	comments = cstr(comments).strip()
	if action not in ("approve", "return", "reject", "rebase"):
		frappe.throw(_("Choose a valid project review action."))
	if action != "approve" and not comments:
		frappe.throw(_("Comments are required when returning, rejecting or refreshing a request."))
	if data is not None:
		patch = _data(
			data, frappe.get_doc("Project", doc.project) if doc.request_kind == "Project Change" else None
		)
		before = json.loads(doc.proposal_data or "{}")
		doc.proposal_data = json.dumps(patch, sort_keys=True)
		doc.title = patch.get("project_name") or doc.title
		if before != patch:
			_event(doc, "Manager edited request", comments, before, patch)
	if action == "rebase":
		if doc.request_kind != "Project Change":
			frappe.throw(_("Only project changes have an approved baseline."))
		doc.base_modified = str(frappe.get_doc("Project", doc.project).modified)
		_event(doc, "Manager refreshed approved baseline", comments)
		return _store(doc)
	if action == "approve":
		if doc.request_kind == "Project Change":
			frappe.db.sql("SELECT name FROM `tabProject` WHERE name=%s FOR UPDATE", doc.project)
			if str(frappe.get_doc("Project", doc.project).modified) != doc.base_modified:
				frappe.throw(
					_(
						"The approved project changed. Review the latest details and explicitly refresh the baseline."
					),
					frappe.TimestampMismatchError,
				)
		candidate = _validate_candidate(doc)
		normalised = project_values(candidate)
		stored = json.loads(doc.proposal_data)
		stored["account_budgets"] = normalised["account_budgets"]
		doc.proposal_data = json.dumps(stored, sort_keys=True)
		patch = json.loads(doc.proposal_data)
		if (
			doc.request_kind == "Project Change"
			and cint(patch.get("is_archived"))
			and workspace.has_financial_records(doc.project)
		):
			frappe.throw(_("This project now has financial records and cannot be removed."))
		patch["revision_reason"] = doc.request_reason or comments or f"Approved request {doc.name}"
		if doc.request_kind == "Project Change":
			patch["modified"] = doc.base_modified
		token = _application.set((doc.project if doc.request_kind == "Project Change" else None, doc.name))
		try:
			project = workspace._save_approved_project(
				patch,
				doc.project if doc.request_kind == "Project Change" else None,
				proposed_by=doc.proposed_by,
			)
		finally:
			_application.reset(token)
		doc.project = project["name"]
		doc.proposal_status = "Approved"
		doc.decided_by, doc.decided_on = frappe.session.user, now_datetime()
		from volunteering.volunteering.project_documents import publish

		publish(doc)
	else:
		doc.proposal_status = "Correction Required" if action == "return" else "Rejected"
		doc.decided_by, doc.decided_on = frappe.session.user, now_datetime()
	_event(
		doc,
		{"approve": "Approved", "return": "Returned for correction", "reject": "Rejected"}[action],
		comments,
	)
	return _store(doc)


@frappe.whitelist(methods=["POST"])
def withdraw_proposal(proposal, modified):
	doc = _load(proposal, modified, lock=True)
	if doc.proposal_status not in EDITABLE:
		frappe.throw(_("Only drafts or returned requests may be withdrawn."))
	if doc.proposed_by != frappe.session.user:
		frappe.throw(_("Only the proposer may withdraw this request."), frappe.PermissionError)
	doc.proposal_status = "Withdrawn"
	_event(doc, "Withdrawn")
	return _store(doc)


@frappe.whitelist(methods=["POST"])
def upload_proposal_document(proposal, filename, content, modified, visibility="Basic"):
	doc = _load(proposal, modified, lock=True)
	if doc.proposal_status not in EDITABLE and not (
		_is_assigned_manager(doc) and doc.proposal_status == "Pending Approval"
	):
		frappe.throw(_("Documents may only be added to editable requests."), frappe.PermissionError)
	if doc.proposal_status in EDITABLE and doc.proposed_by != frappe.session.user:
		frappe.throw(
			_("Only the proposer may add documents to a draft or returned request."), frappe.PermissionError
		)
	if not filename or len(content or "") > 14_000_000:
		frappe.throw(_("Choose a supporting document smaller than 10 MB."))
	from frappe.utils.file_manager import save_file

	from volunteering.volunteering.project_documents import writing

	if visibility not in ("Basic", "Financial"):
		frappe.throw(_("Choose Basic or Financial document visibility."))
	with writing():
		file = save_file(filename, content, "Project Proposal", doc.name, decode=True, is_private=1)
		file.project_visibility = visibility
		file.save(ignore_permissions=True)
	_event(doc, "Supporting document added", f"{file.file_name} ({visibility})")
	return _store(doc)


def validate_request_share(share):
	if share.share_doctype == "Project Proposal":
		doc = frappe.get_doc("Project Proposal", share.share_name)
		if share.everyone or not _readable(doc, share.user) or share.write or share.share:
			frappe.throw(
				_("Project requests cannot be shared outside their proposer and Projects Managers."),
				frappe.PermissionError,
			)
	elif share.share_doctype == "File":
		from volunteering.volunteering.project_documents import can_read, scoped

		file = frappe.get_doc("File", share.share_name)
		if scoped(file) and (share.everyone or not can_read(file, share.user) or share.write or share.share):
			frappe.throw(
				_("Project document shares cannot expand membership visibility."), frappe.PermissionError
			)


@frappe.whitelist(methods=["POST"])
def remove_unused_project(project, modified, reason):
	if not workspace.is_project_manager():
		frappe.throw(_("Only Projects Managers may remove unused projects."), frappe.PermissionError)
	doc = _project(project)
	if str(doc.modified) != modified:
		frappe.throw(_("Reload the project before removing it."), frappe.TimestampMismatchError)
	if not cstr(reason).strip():
		frappe.throw(_("Explain why the unused project is being removed."))
	request = save_proposal(
		{"is_archived": 1, "operational_status": "Cancelled"},
		project=project,
		reason=reason,
		assigned_approver=frappe.session.user,
	)
	request = submit_proposal(request["name"], request["modified"])
	return review_proposal(request["name"], "approve", request["modified"], comments=reason)
