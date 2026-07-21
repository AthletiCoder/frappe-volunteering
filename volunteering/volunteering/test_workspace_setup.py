# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate

from volunteering.volunteering.workspace_setup import (
	DASHBOARD_MARKER,
	VOLUNTEERING_EVENT_DYNAMIC_FILTER,
	WORKSPACE_NAME,
	boot_session,
	get_latest_ngo_event,
	sync_volunteering_dashboard_filters,
	sync_volunteering_workspace_dashboard,
)


class IntegrationTestWorkspaceSetup(IntegrationTestCase):
	def create_event(self, title_suffix=None):
		suffix = title_suffix or frappe.generate_hash(length=8)
		return frappe.get_doc(
			{
				"doctype": "NGO Event",
				"title": f"Workspace Event-{suffix}",
				"startdate": nowdate(),
				"enddate": nowdate(),
			}
		).insert(ignore_permissions=True)

	def test_get_latest_ngo_event_returns_most_recently_created(self):
		older_event = self.create_event("older")
		latest_event = self.create_event("latest")

		self.assertEqual(get_latest_ngo_event(), latest_event.name)
		self.assertNotEqual(get_latest_ngo_event(), older_event.name)

	def test_boot_session_sets_latest_event(self):
		latest_event = self.create_event("boot")
		bootinfo = frappe._dict()

		boot_session(bootinfo)

		self.assertEqual(bootinfo.volunteering_latest_event, latest_event.name)

	def test_sync_volunteering_dashboard_filters_replaces_removed_settings_reference(self):
		if not frappe.db.exists("Number Card", "Total Registrations"):
			self.skipTest("Volunteering dashboard widgets are not installed")

		frappe.db.set_value(
			"Number Card",
			"Total Registrations",
			"dynamic_filters_json",
			'[["Participation","event","=","frappe.db.get_single_value(\\"Volunteering Settings\\", \\"dashboard_event\\")"]]',
			update_modified=False,
		)

		sync_volunteering_dashboard_filters()

		self.assertEqual(
			frappe.db.get_value("Number Card", "Total Registrations", "dynamic_filters_json"),
			VOLUNTEERING_EVENT_DYNAMIC_FILTER,
		)

	def test_sync_volunteering_workspace_dashboard_upgrades_bare_workspace(self):
		if not frappe.db.exists("Workspace", WORKSPACE_NAME):
			self.skipTest("Volunteering workspace is not installed")

		workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
		workspace.content = '[{"id":"header","type":"header","data":{"text":"<span class=\\"h4\\">Volunteering Workspace</span>","col":12}}]'
		workspace.charts = []
		workspace.number_cards = []
		workspace.shortcuts = []
		workspace.flags.ignore_links = True
		workspace.save(ignore_permissions=True)

		sync_volunteering_workspace_dashboard()
		workspace.reload()

		self.assertIn(DASHBOARD_MARKER, workspace.content or "")
		self.assertTrue(workspace.charts)
		self.assertTrue(workspace.number_cards)
		self.assertTrue(workspace.shortcuts)

	def test_sync_volunteering_workspace_dashboard_is_idempotent(self):
		if not frappe.db.exists("Workspace", WORKSPACE_NAME):
			self.skipTest("Volunteering workspace is not installed")

		sync_volunteering_workspace_dashboard()
		workspace = frappe.get_doc("Workspace", WORKSPACE_NAME)
		content = workspace.content
		chart_count = len(workspace.charts)

		sync_volunteering_workspace_dashboard()
		workspace.reload()

		self.assertEqual(workspace.content, content)
		self.assertEqual(len(workspace.charts), chart_count)
