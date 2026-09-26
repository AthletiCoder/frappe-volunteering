# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import math
from collections import defaultdict

import frappe
from frappe import _
from frappe.utils import cint, flt

from volunteering.volunteering.accounting_dashboard.constants import ACCOUNTS_ROLES
from volunteering.volunteering.approval_routing import get_document_amount as get_document_amount
from volunteering.volunteering.authority import BOARD_OF_DIRECTORS, user_has_board_of_directors
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	get_accounting_settings,
)

# A Purchase Order commits budget. Its Purchase Invoice settles that commitment,
# so counting both would double-count the same spend. Employee Advances are staff
# float; the budget is committed by the eventual Expense Claim.
BUDGET_TRACKED_DOCTYPES = ("Expense Claim", "Purchase Order")
CLOSED_PROJECT_CHECK_DOCTYPES = (*BUDGET_TRACKED_DOCTYPES, "Purchase Invoice")
EXCLUDED_WORKFLOW_STATES = ("Draft", "Rejected", "")
CONTROL_MODES = ("No Control", "Warn Only", "Strict")
UNASSIGNED_ACCOUNT = "__unassigned__"


def _project_budget_fields(project):
	if not project:
		return frappe._dict()
	return (
		frappe.db.get_value(
			"Project",
			project,
			[
				"company",
				"budget_status",
				"project_budget_control",
				"total_approved_budget",
				"account_budget_control",
			],
			as_dict=True,
		)
		or frappe._dict()
	)


def get_allocated_budget(project, department=None):
	"""Compatibility alias: department is intentionally ignored."""
	return get_project_total_allocated(project)


def get_project_total_allocated(project):
	if not project or not frappe.db.has_column("Project", "total_approved_budget"):
		return 0
	return flt(frappe.db.get_value("Project", project, "total_approved_budget"))


def _get_account_budget_rows(project):
	if not project or not frappe.db.exists("DocType", "Project Account Budget"):
		return []
	return frappe.get_all(
		"Project Account Budget",
		filters={"parent": project, "parenttype": "Project"},
		fields=["budget_key", "employee_label", "expense_account", "approved_amount", "is_active"],
		order_by="idx asc",
	)


def get_account_allocated_budget(project, account):
	if not project or not account:
		return 0
	return sum(
		flt(row.approved_amount)
		for row in _get_account_budget_rows(project)
		if row.expense_account == account
	)


def get_document_label_amounts(doc):
	amounts = defaultdict(float)
	approved = doc.get("workflow_state") in ("Pending Accounts Classification", "Approved")
	for row in doc.get("expenses") or []:
		amounts[row.get("project_expense_account") or UNASSIGNED_ACCOUNT] += _expense_claim_row_amount(
			row, approved
		)
	return dict(amounts)


def get_project_label_consumption(project, exclude=None):
	amounts = defaultdict(float)
	for row in _active_budget_documents("Expense Claim", project):
		if exclude == ("Expense Claim", row.name):
			continue
		for key, amount in get_document_label_amounts(frappe.get_doc("Expense Claim", row.name)).items():
			amounts[key] += amount
	# PO lines have ledger accounts rather than labels. Attribute them to the
	# label only when that mapping is unambiguous; shared-account commitments
	# are still checked by the aggregate account envelope below.
	by_account = defaultdict(list)
	for row in _get_account_budget_rows(project):
		if row.expense_account:
			by_account[row.expense_account].append(row.budget_key)
	for row in _active_budget_documents("Purchase Order", project):
		if exclude == ("Purchase Order", row.name):
			continue
		for account, amount in get_document_account_amounts(
			frappe.get_doc("Purchase Order", row.name)
		).items():
			if len(by_account[account]) == 1:
				amounts[by_account[account][0]] += amount
	return dict(amounts)


def _account_allocations(project):
	allocations = defaultdict(float)
	for row in _get_account_budget_rows(project):
		if row.expense_account:
			allocations[row.expense_account] += flt(row.approved_amount)
	return dict(allocations)


def _active_budget_documents(doctype, project):
	if not project or not frappe.db.has_column(doctype, "project"):
		return []
	filters = {"project": project, "docstatus": ["!=", 2]}
	if frappe.db.has_column(doctype, "workflow_state"):
		filters["workflow_state"] = ["not in", list(EXCLUDED_WORKFLOW_STATES)]
	return frappe.get_all(doctype, filters=filters, fields=["name", "workflow_state"])


def _expense_claim_row_amount(row, approved=False):
	if approved:
		if row.get("base_sanctioned_amount") is not None:
			return flt(row.get("base_sanctioned_amount"))
		if row.get("sanctioned_amount") is not None:
			return flt(row.get("sanctioned_amount"))
	return flt(row.get("base_amount") or row.get("amount"))


def _purchase_order_row_amount(row):
	return flt(row.get("base_amount") or row.get("amount"))


def get_document_account_amounts(doc):
	"""Return base-currency committed amount by trusted Expense Account."""
	amounts = defaultdict(float)
	if doc.doctype == "Expense Claim":
		approved = doc.get("workflow_state") in ("Pending Accounts Classification", "Approved")
		if doc.get("account_allocations"):
			for allocation in doc.get("account_allocations"):
				amounts[allocation.expense_account or UNASSIGNED_ACCOUNT] += flt(
					allocation.allocated_amount
				) * flt(doc.get("exchange_rate") or 1)
			return dict(amounts)
		for row in doc.get("expenses") or []:
			account = row.get("default_account") or UNASSIGNED_ACCOUNT
			amounts[account] += _expense_claim_row_amount(row, approved=approved)
	elif doc.doctype == "Purchase Order":
		for row in doc.get("items") or []:
			account = row.get("expense_account") or UNASSIGNED_ACCOUNT
			amounts[account] += _purchase_order_row_amount(row)
	return dict(amounts)


def _get_budget_document_amount(doc):
	account_amounts = get_document_account_amounts(doc)
	if account_amounts:
		return sum(account_amounts.values())
	if doc.doctype == "Expense Claim":
		return flt(doc.get("base_total_claimed_amount") or doc.get("total_claimed_amount"))
	if doc.doctype == "Purchase Order":
		return flt(doc.get("base_grand_total") or doc.get("grand_total"))
	return 0


def get_consumed_amount(project, department=None, exclude=None):
	"""Committed amount for the whole Project; department is ignored for compatibility."""
	if not project:
		return 0
	total = 0
	for doctype in BUDGET_TRACKED_DOCTYPES:
		for row in _active_budget_documents(doctype, project):
			if exclude and exclude == (doctype, row.name):
				continue
			total += _get_budget_document_amount(frappe.get_doc(doctype, row.name))
	return total


def get_budget_commitment_breakdown(project):
	"""Explain whole-Project commitment without changing budget enforcement semantics.

	Pending claims and Purchase Orders reserve budget. Approved Expense Claims are
	shown separately because they have become accounting expenditure, although all
	three categories remain part of the same committed total used by budget checks.
	"""
	allocated = get_project_total_allocated(project)
	pending_claims = 0
	approved_expenditure = 0
	for row in _active_budget_documents("Expense Claim", project):
		amount = _get_budget_document_amount(frappe.get_doc("Expense Claim", row.name))
		if row.workflow_state == "Approved":
			approved_expenditure += amount
		else:
			pending_claims += amount

	purchase_orders = sum(
		_get_budget_document_amount(frappe.get_doc("Purchase Order", row.name))
		for row in _active_budget_documents("Purchase Order", project)
	)
	pending_commitments = pending_claims + purchase_orders
	total_committed = pending_commitments + approved_expenditure
	return {
		"has_project_budget": bool(allocated),
		"approved_budget": allocated,
		"pending_claim_commitments": pending_claims,
		"purchase_order_commitments": purchase_orders,
		"pending_commitments": pending_commitments,
		"approved_expenditure": approved_expenditure,
		"total_committed": total_committed,
		"available_after_commitments": allocated - total_committed,
	}


def get_account_consumed_amount(project, account, exclude=None):
	if not project or not account:
		return 0
	total = 0
	for doctype in BUDGET_TRACKED_DOCTYPES:
		for row in _active_budget_documents(doctype, project):
			if exclude and exclude == (doctype, row.name):
				continue
			amounts = get_document_account_amounts(frappe.get_doc(doctype, row.name))
			total += flt(amounts.get(account))
	return total


def get_project_account_consumption(project, exclude=None):
	amounts = defaultdict(float)
	if not project:
		return {}
	for doctype in BUDGET_TRACKED_DOCTYPES:
		for row in _active_budget_documents(doctype, project):
			if exclude and exclude == (doctype, row.name):
				continue
			for account, amount in get_document_account_amounts(frappe.get_doc(doctype, row.name)).items():
				amounts[account] += flt(amount)
	return dict(amounts)


def _overspend_pct(allocated, proposed):
	if allocated <= 0 or proposed <= allocated:
		return 0
	return ((proposed - allocated) / allocated) * 100


def _is_approving(doc):
	"""True when this save is transitioning into Approved."""
	target = "Pending Accounts Classification" if doc.doctype == "Expense Claim" else "Approved"
	if doc.get("workflow_state") != target:
		return False
	previous = doc.get_doc_before_save()
	return not previous or previous.get("workflow_state") != target


def _can_override_budget(settings=None):
	"""Board of Directors grade overrides; an optional configured role still works."""
	if user_has_board_of_directors(frappe.session.user):
		return True
	settings = settings or get_accounting_settings()
	override_role = settings.get("budget_override_role")
	return bool(override_role) and override_role in frappe.get_roles(frappe.session.user)


def user_can_override_budget():
	return _can_override_budget(get_accounting_settings())


# Legacy alias for callers/tests still on the role-only name.
_has_budget_override_role = _can_override_budget


def _format_overrun(label, allocated, proposed):
	over_by = proposed - allocated
	over_pct = _overspend_pct(allocated, proposed)
	return _("{0}: committed {1} against {2}; over by {3} ({4}%).").format(
		label,
		frappe.format_value(proposed, "Currency"),
		frappe.format_value(allocated, "Currency"),
		frappe.format_value(over_by, "Currency"),
		frappe.utils.rounded(over_pct, 1),
	)


def _budget_violations(doc, project_values, exclude):
	violations = []
	total_control = project_values.get("project_budget_control") or "No Control"
	total_allocated = flt(project_values.get("total_approved_budget"))
	if total_control != "No Control" and total_allocated:
		proposed = get_consumed_amount(doc.project, exclude=exclude) + _get_budget_document_amount(doc)
		if proposed > total_allocated:
			violations.append(
				frappe._dict(
					mode=total_control,
					message=_format_overrun(_("Overall Project budget"), total_allocated, proposed),
				)
			)

	account_control = project_values.get("account_budget_control") or "No Control"
	if account_control == "No Control":
		return violations

	if doc.doctype == "Expense Claim":
		labels = {row.budget_key: row for row in _get_account_budget_rows(doc.project)}
		consumption = get_project_label_consumption(doc.project, exclude=exclude)
		for key, amount in get_document_label_amounts(doc).items():
			if not amount:
				continue
			row = labels.get(key)
			if not row:
				message = _("Expense category budget: select a label approved for this project.")
			elif flt(consumption.get(key)) + amount > flt(row.approved_amount):
				message = _format_overrun(
					_("Expense category {0}").format(row.employee_label),
					flt(row.approved_amount),
					flt(consumption.get(key)) + amount,
				)
			else:
				continue
			violations.append(frappe._dict(mode=account_control, message=message))
	# Expense Claim break-up budgets are enforced by their employee-facing label.
	# Project account mappings are suggestions, not allocations, and may contain
	# several accounts. Final claim allocations are therefore not compared with a
	# fictitious per-account project ceiling.
	if doc.doctype == "Expense Claim":
		return violations
	allocations = _account_allocations(doc.project)
	existing_consumption = get_project_account_consumption(doc.project, exclude=exclude)
	for account, document_amount in get_document_account_amounts(doc).items():
		if not document_amount:
			continue
		if account == UNASSIGNED_ACCOUNT:
			message = _(
				"Expense Account budget: an expense line has no Expense Account. "
				"Choose an account linked to the Project or set the Purchase Order item account."
			)
		elif account not in allocations:
			message = _("Expense Account budget: {0} has no allocation on Project {1}.").format(
				account, doc.project
			)
		else:
			allocated = allocations[account]
			proposed = flt(existing_consumption.get(account)) + document_amount
			if proposed <= allocated:
				continue
			message = _format_overrun(_("Expense Account {0}").format(account), allocated, proposed)
		violations.append(frappe._dict(mode=account_control, message=message))
	return violations


def get_strict_budget_violations(doc):
	"""Current strict overruns, including this saved pending document."""
	if doc.doctype not in BUDGET_TRACKED_DOCTYPES or not doc.get("project"):
		return []
	exclude = None if doc.is_new() else (doc.doctype, doc.name)
	return [
		row.message
		for row in _budget_violations(doc, _project_budget_fields(doc.project), exclude)
		if row.mode == "Strict"
	]


def validate_budget_on_save(doc, method=None):
	if doc.doctype not in CLOSED_PROJECT_CHECK_DOCTYPES or not doc.get("project"):
		return

	project_values = _project_budget_fields(doc.project)
	if project_values.get("budget_status") == "Closed":
		frappe.throw(_("Project {0} budget is Closed. Choose an Active project.").format(doc.project))

	if doc.doctype not in BUDGET_TRACKED_DOCTYPES:
		return
	if doc.get("workflow_state") in EXCLUDED_WORKFLOW_STATES:
		refresh_project_budget_status(doc.project)
		return

	exclude = None if doc.is_new() else (doc.doctype, doc.name)
	violations = _budget_violations(doc, project_values, exclude)
	if not violations:
		refresh_project_budget_status(doc.project)
		return

	warnings = [row.message for row in violations if row.mode == "Warn Only"]
	strict = [row.message for row in violations if row.mode == "Strict"]
	if warnings:
		frappe.msgprint("<br>".join(warnings), indicator="orange", title=_("Budget Warning"))

	if strict and _is_approving(doc):
		reason = (doc.get("budget_override_reason") or "").strip()
		message = "<br>".join(strict)
		if not reason:
			frappe.throw(
				_("{0}<br>Enter a Budget Exceedance Reason, then Approve again.").format(message),
				title=_("Strict Budget Override Reason Required"),
			)
		settings = get_accounting_settings()
		if not _can_override_budget(settings):
			override_authority = settings.get("budget_override_role") or BOARD_OF_DIRECTORS
			frappe.throw(
				_("{0}<br>Escalate this claim to {1} for an authorised override.").format(
					message, override_authority
				),
				title=_("Strict Budget Block"),
			)
		frappe.msgprint(
			_("Strict budget override recorded: {0}").format(reason),
			indicator="orange",
			title=_("Budget Override Applied"),
		)
	elif strict:
		frappe.msgprint(
			"<br>".join(strict),
			indicator="orange",
			title=_("Strict Budget Will Require Authorised Override"),
		)

	refresh_project_budget_status(doc.project)


def refresh_project_budget_status(project):
	"""Exhausted reflects only the independent whole-Project ceiling."""
	if not project or not frappe.db.has_column("Project", "budget_status"):
		return
	values = _project_budget_fields(project)
	if values.get("budget_status") == "Closed":
		return
	allocated = flt(values.get("total_approved_budget"))
	new_status = "Exhausted" if allocated and get_consumed_amount(project) >= allocated else "Active"
	if values.get("budget_status") != new_status:
		frappe.db.set_value("Project", project, "budget_status", new_status, update_modified=False)


@frappe.whitelist()
def get_budget_snapshot(project, department=None):
	"""Whole-Project and Expense Account utilisation; department is ignored."""
	if not project:
		return {}
	project_doc = frappe.get_doc("Project", project)
	project_doc.check_permission("read")
	from volunteering.volunteering.project_workspace import can_view_finance

	if not can_view_finance(project_doc):
		return {}
	values = _project_budget_fields(project)
	allocated = flt(values.get("total_approved_budget"))
	breakdown = get_budget_commitment_breakdown(project)
	consumed = breakdown["total_committed"]
	account_allocations = _account_allocations(project)
	account_consumption = get_project_account_consumption(project)
	accounts = []
	for account in sorted(set(account_allocations) | set(account_consumption)):
		account_allocated = flt(account_allocations.get(account))
		account_consumed = flt(account_consumption.get(account))
		accounts.append(
			{
				"expense_account": account,
				"is_budgeted": account in account_allocations,
				"allocated": account_allocated,
				"consumed": account_consumed,
				"remaining": account_allocated - account_consumed,
				"utilisation_pct": (account_consumed / account_allocated * 100 if account_allocated else 0),
			}
		)
	# Whole-Project utilisation is useful to staff. Per-account allocations and
	# consumption remain finance-only; the employee selector has a separate API
	# that returns names without any figures.
	can_view_account_details = True
	return {
		"project": project,
		"budget_status": values.get("budget_status") or "Active",
		"project_control": values.get("project_budget_control") or "No Control",
		"account_control": values.get("account_budget_control") or "No Control",
		"has_project_budget": bool(allocated),
		"allocated": allocated,
		"consumed": consumed,
		"remaining": allocated - consumed,
		"utilisation_pct": (consumed / allocated * 100) if allocated else 0,
		"financial_status": breakdown,
		"accounts": accounts if can_view_account_details else [],
	}


def validate_project_budgets(doc, method=None):
	project_control = doc.get("project_budget_control") or "No Control"
	account_control = doc.get("account_budget_control") or "No Control"
	if project_control not in CONTROL_MODES or account_control not in CONTROL_MODES:
		frappe.throw(_("Budget Control must be No Control, Warn Only, or Strict."))
	if project_control != "No Control" and flt(doc.get("total_approved_budget")) <= 0:
		frappe.throw(_("Enter a Total Approved Budget when Overall Project Budget Control is enabled."))

	seen = set()
	keys = set()
	active_seen = set()
	for row in doc.get("account_budgets") or []:
		account = row.get("expense_account")
		label = " ".join((row.get("employee_label") or "").split())
		if not label and account and not cint(doc.get("project_setup_version")):
			label = frappe.db.get_value("Account", account, "account_name") or account
		if not label or len(label) > 140:
			frappe.throw(_("Enter an expense break up label (at most 140 characters)."))
		if label.casefold() in seen:
			frappe.throw(_("Expense label {0} appears more than once.").format(label))
		seen.add(label.casefold())
		row.employee_label = label
		row.budget_key = row.get("budget_key") or frappe.generate_hash(length=20)
		if row.budget_key in keys or len(row.budget_key) > 140:
			frappe.throw(_("Invalid or duplicate expense label ID."))
		keys.add(row.budget_key)
		amount = flt(row.get("approved_amount"))
		if not math.isfinite(amount) or amount < 0:
			frappe.throw(_("Expense label allocations must be finite, non-negative amounts."))
		if cint(row.get("is_active")):
			active_seen.add(row.budget_key)
		if (
			account_control != "No Control"
			and cint(row.get("is_active"))
			and flt(row.get("approved_amount")) <= 0
		):
			frappe.throw(_("Enter an approved amount greater than zero for {0}.").format(label))
		if not account:
			continue
		account_values = frappe.db.get_value(
			"Account", account, ["company", "root_type", "is_group", "disabled"], as_dict=True
		)
		if not account_values:
			frappe.throw(_("Expense Account {0} does not exist.").format(account))
		if doc.get("company") and account_values.company != doc.company:
			frappe.throw(_("Expense Account {0} belongs to a different Company.").format(account))
		if account_values.root_type != "Expense" or account_values.is_group or account_values.disabled:
			frappe.throw(_("{0} must be an enabled, non-group Expense Account.").format(account))

	if account_control != "No Control" and not active_seen:
		frappe.throw(
			_("Make at least one expense label available when expense category budget control is enabled.")
		)

	if doc.get("budget_status") != "Closed" and not doc.is_new():
		allocated = flt(doc.get("total_approved_budget"))
		doc.budget_status = (
			"Exhausted" if allocated and get_consumed_amount(doc.name) >= allocated else "Active"
		)


# Compatibility name for integrations that imported the former validator.
validate_project_department_budgets = validate_project_budgets


@frappe.whitelist()
def get_budget_health(project=None):
	"""Return one whole-Project row with nested Expense Account allocations."""
	frappe.has_permission("Project", "read", throw=True)
	filters = {"name": project} if project else {}
	projects = frappe.get_list(
		"Project",
		filters=filters,
		limit_page_length=0,
		fields=[
			"name",
			"project_type",
		],
	)
	rows = []
	for project_row in projects:
		snapshot = get_budget_snapshot(project_row.name)
		if not snapshot:
			continue
		rows.append(
			{
				"project": project_row.name,
				"project_type": project_row.get("project_type"),
				"budget_status": snapshot.get("budget_status"),
				"project_control": snapshot.get("project_control"),
				"account_control": snapshot.get("account_control"),
				"has_project_budget": snapshot.get("has_project_budget"),
				"allocated": snapshot.get("allocated"),
				"consumed": snapshot.get("consumed"),
				"remaining": snapshot.get("remaining"),
				"utilisation_pct": snapshot.get("utilisation_pct"),
				"accounts": snapshot.get("accounts"),
				"route": f"/desk/project/{project_row.name}",
			}
		)
	return rows
