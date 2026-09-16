# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Project-scoped Expense Account selection without Chart of Accounts access."""

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
		fields=["expense_account", "employee_label", "is_active"],
		order_by="idx asc",
	)


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
	"""Resolve the safe employee selector into HRMS' hidden ledger field.

	The selector is an Autocomplete/Data field, not a Link, so an employee never
	needs Account DocPerm. Every value is checked against the selected Project's
	active allow-list before it is copied to ``default_account`` for GL posting.
	"""
	if doc.doctype != "Expense Claim":
		return
	project = _project_values(doc.get("project"))
	if not project:
		frappe.throw(_("Select a Project before choosing Expense Accounts."))
	if doc.get("company") and project.company and doc.company != project.company:
		frappe.throw(_("Project {0} belongs to a different Company.").format(doc.project))

	allowed = {row.expense_account: row for row in _account_rows(doc.project, active_only=True)}
	if not allowed:
		frappe.throw(
			_(
				"Project {0} has no Expense Accounts available to employees. Ask an Accounts administrator to configure the Project."
			).format(doc.project),
			title=_("Project Expense Accounts Missing"),
		)

	previous = doc.get_doc_before_save()
	previous_rows = {row.name: row for row in (previous.get("expenses") or [])} if previous else {}
	changes = []
	for row in doc.get("expenses") or []:
		selected = _selected_account(row, permit_legacy_fallback=bool(previous and row.name))
		if not selected:
			frappe.throw(_("Row {0}: Select a Project Expense Account.").format(row.idx))
		if selected not in allowed:
			frappe.throw(
				_("Row {0}: Expense Account {1} is not available for Project {2}.").format(
					row.idx, selected, doc.project
				),
				title=_("Expense Account Not Allowed"),
			)
		_validate_account(selected, project.company or doc.company)

		old_row = previous_rows.get(row.name)
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
					_("Only Accounts can change an Expense Account after the claim is submitted."),
					frappe.PermissionError,
				)
			changes.append((row.idx, old_account, selected))

		row.project_expense_account = selected
		row.default_account = selected
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
		frappe.throw(_("Please log in to view Project Expense Accounts."), frappe.PermissionError)
	values = _project_values(project)
	if not values:
		return []
	project_doc = frappe.get_doc("Project", project)
	project_doc.check_permission("read")
	if company and values.company and company != values.company:
		return []

	needle = cstr(txt).strip().casefold()
	options = []
	for row in _account_rows(project, active_only=True):
		account = _account_details(row.expense_account)
		if not account or account.company != values.company:
			continue
		if account.root_type != "Expense" or cint(account.is_group) or cint(account.disabled):
			continue
		friendly = cstr(row.employee_label).strip() or account.account_name or account.name
		haystack = f"{friendly} {account.account_name or ''} {account.name}".casefold()
		if needle and needle not in haystack:
			continue
		label = friendly if friendly == account.name else f"{friendly} — {account.name}"
		options.append(
			{
				"value": account.name,
				"label": label,
				"description": _("Available for Project {0}").format(project),
			}
		)
	return options


def add_account_change_audit_comment(doc, method=None) -> None:
	"""Record Accounts corrections without exposing account records to employees."""
	changes = getattr(doc.flags, "project_expense_account_changes", None) or []
	if not changes:
		return
	lines = []
	for idx, old_account, new_account in changes:
		lines.append(
			_("Row {0}: {1} → {2}").format(
				idx,
				escape_html(old_account or _("not set")),
				escape_html(new_account),
			)
		)
	doc.add_comment(
		"Info",
		_("Expense Account selection changed by {0}:<br>{1}").format(
			escape_html(frappe.session.user), "<br>".join(lines)
		),
	)
