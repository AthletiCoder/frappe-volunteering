# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import os

import frappe


def get_context(context):
	frappe.only_for(("Employee", "Accounts User", "Accounts Manager", "System Manager", "HR Manager"))
	context.no_cache = 1
	context.csrf_token = frappe.sessions.get_csrf_token()

	frontend_dir = frappe.get_app_path("volunteering", "public", "frontend", "assets")
	entry_js = None
	entry_css = None
	if os.path.isdir(frontend_dir):
		for name in os.listdir(frontend_dir):
			if name.startswith("index-") and name.endswith(".js"):
				entry_js = name
			if name.startswith("index-") and name.endswith(".css"):
				entry_css = name
	context.has_spa_build = 1 if entry_js else 0
	context.spa_entry_js = entry_js or ""
	context.spa_entry_css = entry_css or ""
	return context
