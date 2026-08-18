# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import os

import frappe


def get_context(context):
	frappe.only_for(
		(
			"Employee",
			"Accounts User",
			"Accounts Manager",
			"System Manager",
			"HR Manager",
			"HR User",
			"NGO Coordinator",
			"Leave Approver",
			"Expense Approver",
		)
	)
	context.no_cache = 1
	context.full_width = 1
	context.csrf_token = frappe.sessions.get_csrf_token()

	frontend_dir = frappe.get_app_path("volunteering", "public", "frontend", "assets")
	entry_js = None
	entry_css = None
	if os.path.isdir(frontend_dir):
		js_names = []
		css_names = []
		for name in os.listdir(frontend_dir):
			if name.startswith("index-") and name.endswith(".js"):
				js_names.append(name)
			if name.startswith("index-") and name.endswith(".css"):
				css_names.append(name)
		js_names.sort(key=lambda n: os.path.getmtime(os.path.join(frontend_dir, n)), reverse=True)
		css_names.sort(key=lambda n: os.path.getmtime(os.path.join(frontend_dir, n)), reverse=True)
		entry_js = js_names[0] if js_names else None
		entry_css = css_names[0] if css_names else None
	context.has_spa_build = 1 if entry_js else 0
	context.spa_entry_js = entry_js or ""
	context.spa_entry_css = entry_css or ""
	return context
