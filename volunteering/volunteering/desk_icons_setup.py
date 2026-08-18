# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Desk home-wall icons: SPA pages + Help."""

from __future__ import annotations

import frappe

from volunteering.volunteering.accounting_setup import BUDGET_HEALTH_ROLES
from volunteering.volunteering.home_service import (
	ADVANCES_URL,
	BUDGET_HEALTH_URL,
	HOME_URL,
	TODOS_URL,
)

HOME_ROLES = (
	"Employee",
	"Accounts User",
	"Accounts Manager",
	"NGO Coordinator",
	"HR Manager",
	"HR User",
	"System Manager",
	"Leave Approver",
	"Expense Approver",
)
WIKI_ROLES = ("Employee", "Accounts User", "Accounts Manager", "System Manager")

HIDE_LABELS = (
	"Quick Links",
	"How to Spend",
	"My Approval",
	"My Work",
	"My Expenses",
)

BUDGET_ROLES = BUDGET_HEALTH_ROLES + ("System Manager",)

EXTERNAL_ICONS = (
	{
		"label": "Home",
		"icon_type": "Link",
		"link_type": "External",
		"link": HOME_URL,
		"icon": "home",
		"roles": HOME_ROLES,
	},
	{
		"label": "To-do",
		"icon_type": "Link",
		"link_type": "External",
		"link": TODOS_URL,
		"icon": "check",
		"roles": HOME_ROLES,
	},
	{
		"label": "Advance Portal",
		"icon_type": "Link",
		"link_type": "External",
		"link": ADVANCES_URL,
		"icon": "money-coins-1",
		"roles": HOME_ROLES,
	},
	{
		"label": "Budget Health",
		"icon_type": "Link",
		"link_type": "External",
		"link": BUDGET_HEALTH_URL,
		"icon": "pie-chart",
		"roles": BUDGET_ROLES,
	},
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
		for spec in EXTERNAL_ICONS:
			_upsert_icon(spec)
		_migrate_quick_links_to_home()
		for label in HIDE_LABELS:
			_hide_icon(label)
	except Exception:
		frappe.log_error(title="Desk icons setup failed", message=frappe.get_traceback())


def _ensure_sidebars_exist():
	from volunteering.volunteering.quick_links_setup import ensure_my_work
	from volunteering.volunteering.accounts_workspace_setup import ensure_my_expenses

	ensure_my_work()
	ensure_my_expenses()


def _migrate_quick_links_to_home():
	"""Hide leftover Quick Links / My Work tiles; Home is the product entry."""
	for label in ("Quick Links", "My Work", "My Expenses"):
		_hide_icon(label)


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
