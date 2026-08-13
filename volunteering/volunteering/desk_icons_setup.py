# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Desk home-wall icons: My Work, My Expenses, Wiki."""

from __future__ import annotations

import frappe

EMPLOYEE_ROLES = ("Employee", "System Manager")
EXPENSE_ROLES = (
	"Employee",
	"Accounts User",
	"Accounts Manager",
	"NGO Coordinator",
	"System Manager",
)
WIKI_ROLES = ("Employee", "Accounts User", "Accounts Manager", "System Manager")

# Hide legacy / clutter tiles
HIDE_LABELS = (
	"Quick Links",
	"How to Spend",
	"My Approval",
	"Budget Health",  # reachable from My Expenses
)

SIDEBAR_ICONS = (
	{
		"label": "My Work",
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": "My Work",
		"icon": "briefcase",
		"roles": EMPLOYEE_ROLES,
	},
	{
		"label": "My Expenses",
		"icon_type": "Link",
		"link_type": "Workspace Sidebar",
		"link_to": "My Expenses",
		"icon": "expense",
		"roles": EXPENSE_ROLES,
	},
)

EXTERNAL_ICONS = (
	{
		"label": "Wiki",
		"icon_type": "Link",
		"link_type": "External",
		"link": "/help",
		"icon": "book",
		"roles": WIKI_ROLES,
	},
)


def ensure_desk_icons():
	try:
		_ensure_sidebars_exist()
		for spec in SIDEBAR_ICONS + EXTERNAL_ICONS:
			_upsert_icon(spec)
		# Prefer My Work over legacy Quick Links that already points at My Work sidebar
		_migrate_quick_links_to_my_work()
		for label in HIDE_LABELS:
			_hide_icon(label)
	except Exception:
		frappe.log_error(title="Desk icons setup failed", message=frappe.get_traceback())


def _ensure_sidebars_exist():
	from volunteering.volunteering.quick_links_setup import ensure_my_work
	from volunteering.volunteering.accounts_workspace_setup import ensure_my_expenses

	ensure_my_work()
	ensure_my_expenses()


def _migrate_quick_links_to_my_work():
	"""If Quick Links exists and My Work does not, rename; else hide Quick Links."""
	if not frappe.db.exists("Desktop Icon", "Quick Links"):
		return
	if frappe.db.exists("Desktop Icon", "My Work"):
		_hide_icon("Quick Links")
		return
	frappe.rename_doc("Desktop Icon", "Quick Links", "My Work", force=True, merge=False)
	doc = frappe.get_doc("Desktop Icon", "My Work")
	doc.link_type = "Workspace Sidebar"
	doc.link_to = "My Work"
	doc.link = None
	doc.icon = "briefcase"
	doc.hidden = 0
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)


def _upsert_icon(spec: dict):
	label = spec["label"]
	if frappe.db.exists("Desktop Icon", label):
		doc = frappe.get_doc("Desktop Icon", label)
		doc.icon_type = spec["icon_type"]
		doc.link_type = spec["link_type"]
		doc.link_to = spec.get("link_to")
		doc.link = spec.get("link")
		doc.icon = spec.get("icon")
		doc.hidden = 0
		doc.app = "volunteering"
		_sync_roles(doc, spec.get("roles") or ())
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc(
		{
			"doctype": "Desktop Icon",
			"label": label,
			"icon_type": spec["icon_type"],
			"link_type": spec["link_type"],
			"link_to": spec.get("link_to"),
			"link": spec.get("link"),
			"icon": spec.get("icon"),
			"standard": 0,
			"hidden": 0,
			"app": "volunteering",
		}
	)
	_sync_roles(doc, spec.get("roles") or ())
	doc.insert(ignore_permissions=True)


def _sync_roles(doc, roles):
	wanted = {r for r in roles if frappe.db.exists("Role", r)}
	existing = {row.role for row in doc.roles or []}
	if existing == wanted:
		return
	doc.set("roles", [])
	for role in sorted(wanted):
		doc.append("roles", {"role": role})


def _hide_icon(label: str):
	if not frappe.db.exists("Desktop Icon", label):
		return
	frappe.db.set_value("Desktop Icon", label, "hidden", 1)
