# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Project-scoped expense-label selection without Chart of Accounts access."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, cstr, escape_html

from volunteering.volunteering.accounting_dashboard.constants import ACCOUNTS_ROLES

EMPLOYEE_EDITABLE_STATES = frozenset({"Draft", "Receipt Correction Required", "Rejected"})


def _project_values(project: str | None) -> frappe._dict:
	if not project:
		return frappe._dict()
	return (
		frappe.db.get_value("Project", project, ["name", "company", "budget_status"], as_dict=True)
		or frappe._dict()
	)


def _account_rows(project: str, *, active_only: bool = False) -> list[frappe._dict]:
	filters = {"parent": project, "parenttype": "Project", "parentfield": "account_budgets"}
	if active_only:
		filters["is_active"] = 1
	return frappe.get_all(
		"Project Account Budget",
		filters=filters,
		fields=["budget_key", "expense_account", "employee_label", "is_active"],
		order_by="idx asc",
	)


def suggested_accounts(project: str, budget_key: str) -> list[str]:
	"""Return optional Accounts-maintained suggestions for one approved label."""
	if frappe.db.exists("DocType", "Project Expense Account Mapping"):
		accounts = frappe.get_all(
			"Project Expense Account Mapping",
			filters={
				"parent": project,
				"parenttype": "Project",
				"parentfield": "expense_account_mappings",
				"budget_key": budget_key,
			},
			pluck="expense_account",
			order_by="idx asc",
		)
		if accounts:
			return list(dict.fromkeys(filter(None, accounts)))
	legacy = frappe.db.get_value(
		"Project Account Budget",
		{"parent": project, "parenttype": "Project", "budget_key": budget_key},
		"expense_account",
	)
	return [legacy] if legacy else []


def _account_details(account: str | None) -> frappe._dict:
	if not account:
		return frappe._dict()
	return (
		frappe.db.get_value(
			"Account",
			account,
			["name", "account_name", "company", "root_type", "is_group", "disabled"],
			as_dict=True,
		)
		or frappe._dict()
	)


def _validate_account(account: str, company: str) -> frappe._dict:
	values = _account_details(account)
	if not values:
		frappe.throw(_("Expense Account {0} does not exist.").format(account))
	if values.company != company:
		frappe.throw(_("Expense Account {0} belongs to a different Company.").format(account))
	if values.root_type != "Expense" or cint(values.is_group) or cint(values.disabled):
		frappe.throw(_("{0} must be an enabled, non-group Expense Account.").format(account))
	return values


def _can_change_after_employee_submission(user: str | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(ACCOUNTS_ROLES.intersection(frappe.get_roles(user)))


def _selected_account(row, *, permit_legacy_fallback: bool) -> str:
	selected = cstr(row.get("project_expense_account")).strip()
	if not selected and permit_legacy_fallback:
		selected = cstr(row.get("default_account")).strip()
	return selected


def assign_and_validate_project_expense_accounts(doc) -> None:
	"""Resolve the safe employee expense-label selector for an HRMS claim.

	The selector is an Autocomplete/Data field, not a Link, so an employee never
	needs Account DocPerm. Every value is checked against the selected Project's
	approved labels. A suggested or temporary account is copied provisionally to
	``default_account`` for draft validation; Accounts replaces it with the final
	allocation before the claim is submitted and posted.
	"""
	if doc.doctype != "Expense Claim":
		return
	project = _project_values(doc.get("project"))
	if not project:
		frappe.throw(_("Select a Project before choosing an expense category."))
	if doc.get("company") and project.company and doc.company != project.company:
		frappe.throw(_("Project {0} belongs to a different Company.").format(doc.project))
	all_rows = _account_rows(doc.project)
	allowed = {row.budget_key: row for row in all_rows if cint(row.is_active)}
	if not allowed:
		frappe.throw(
			_(
				"Project {0} has no expense categories available to employees. Ask a Projects Manager to approve its labels and budgets."
			).format(doc.project),
			title=_("Project Expense Categories Missing"),
		)

	previous = doc.get_doc_before_save()
	previous_rows = {row.name: row for row in (previous.get("expenses") or [])} if previous else {}
	changes = []
	for row in doc.get("expenses") or []:
		old_row = previous_rows.get(row.name) if previous and previous.project == doc.project else None
		selected = _selected_account(row, permit_legacy_fallback=bool(previous and row.name))
		# Compatibility for pre-upgrade saved claims only; new claims must use an
		# opaque label ID, never an arbitrary Account identifier.
		if old_row and selected == old_row.get("default_account"):
			matches = [item.budget_key for item in all_rows if item.expense_account == selected]
			if len(matches) == 1:
				selected = matches[0]
		if not selected:
			frappe.throw(_("Row {0}: Select a Project Expense Category.").format(row.idx))
		if (
			old_row
			and old_row.get("project_expense_account") == selected
			and previous.workflow_state not in EMPLOYEE_EDITABLE_STATES
		):
			# Existing reviewed/approved claims retain their category and provisional
			# account even if the category has since been disabled for new claims.
			row.default_account = old_row.default_account
			row.project_expense_account = selected
			continue
		if selected not in allowed:
			frappe.throw(
				_("Row {0}: Expense category {1} is not available for Project {2}.").format(
					row.idx, selected, doc.project
				),
				title=_("Expense Category Not Allowed"),
			)
		accounts = suggested_accounts(doc.project, selected)
		account = accounts[0] if accounts else None
		if not account:
			from volunteering.volunteering.accounting_setup import ensure_unclassified_expense_account

			account = ensure_unclassified_expense_account(project.company or doc.company)
		if not account:
			frappe.throw(_("No temporary Expense Account is available for this Company."))
		_validate_account(account, project.company or doc.company)

		old_account = (
			cstr(old_row.get("project_expense_account") or old_row.get("default_account")).strip()
			if old_row
			else ""
		)
		if old_row and old_account != selected:
			if (
				previous.workflow_state not in EMPLOYEE_EDITABLE_STATES
				and not _can_change_after_employee_submission()
			):
				frappe.throw(
					_("Only Accounts can change an expense category after the claim is submitted."),
					frappe.PermissionError,
				)
			changes.append((row.idx, old_account, selected))

		row.project_expense_account = selected
		row.default_account = account
		if row.meta.has_field("project"):
			row.project = doc.project

	if changes:
		doc.flags.project_expense_account_changes = changes


@frappe.whitelist()
def get_project_expense_account_options(
	project: str | None = None, company: str | None = None, txt: str = ""
) -> list[dict]:
	"""Return only employee-safe Project account options, never balances/budgets."""
	if frappe.session.user == "Guest":
		frappe.throw(_("Please log in to view Project expense categories."), frappe.PermissionError)
	values = _project_values(project)
	if not values:
		return []
	project_doc = frappe.get_doc("Project", project)
	project_doc.check_permission("read")
	if company and values.company and company != values.company:
		return []

	return employee_options(project_doc, txt)


def employee_options(project_doc, txt=""):
	"""Opaque label IDs and approved labels only; no ledger names or balances."""
	needle = cstr(txt).strip().casefold()
	options = []
	rows = [row for row in project_doc.get("account_budgets") or [] if cint(row.is_active)]
	for row in rows:
		friendly = cstr(row.employee_label).strip()
		if needle and needle not in friendly.casefold():
			continue
		options.append(
			{
				"value": row.budget_key,
				"label": friendly,
				"description": "",
			}
		)
	return options


def add_account_change_audit_comment(doc, method=None) -> None:
	"""Record Accounts corrections without exposing account records to employees."""
	changes = getattr(doc.flags, "project_expense_account_changes", None) or []
	if not changes:
		return
	labels = {
		row.budget_key: row.employee_label for row in _account_rows(doc.get("project")) if row.budget_key
	}
	lines = []
	for idx, old_account, new_account in changes:
		lines.append(
			_("Row {0}: {1} → {2}").format(
				idx,
				escape_html(labels.get(old_account) or _("previous category")),
				escape_html(labels.get(new_account) or _("updated category")),
			)
		)
	doc.add_comment(
		"Info",
		_("Expense category selection changed by {0}:<br>{1}").format(
			escape_html(frappe.session.user), "<br>".join(lines)
		),
	)
