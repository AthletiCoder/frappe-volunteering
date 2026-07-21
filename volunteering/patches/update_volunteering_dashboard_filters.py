import frappe

from volunteering.volunteering.workspace_setup import sync_volunteering_dashboard_filters


def execute():
	sync_volunteering_dashboard_filters()
	frappe.db.commit()
