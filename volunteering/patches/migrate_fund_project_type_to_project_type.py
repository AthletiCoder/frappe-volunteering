"""Migrate Fund Project Type → standard Project Type and drop obsolete custom fields."""

from __future__ import annotations

import frappe

from volunteering.volunteering.accounting_setup import (
	ensure_project_types,
	remove_obsolete_accounting_custom_fields,
	setup_accounting_custom_fields,
)


def execute():
	ensure_project_types()
	setup_accounting_custom_fields()

	if frappe.db.has_column("Project", "fund_project_type") and frappe.db.has_column(
		"Project", "project_type"
	):
		frappe.db.sql(
			"""
			UPDATE `tabProject`
			SET project_type = fund_project_type
			WHERE IFNULL(fund_project_type, '') != ''
				AND IFNULL(project_type, '') = ''
			"""
		)

	remove_obsolete_accounting_custom_fields()
	frappe.clear_cache(doctype="Project")
	frappe.clear_cache(doctype="Expense Claim")
