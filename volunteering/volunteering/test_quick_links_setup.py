# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.quick_links_setup import WORKSPACE_NAME, ensure_my_work


class IntegrationTestMyWork(IntegrationTestCase):
	def test_ensure_my_work_is_idempotent(self):
		ensure_my_work()
		self.assertTrue(
			frappe.db.exists("Workspace", WORKSPACE_NAME)
			or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
		)

		name = (
			frappe.db.exists("Workspace", WORKSPACE_NAME)
			or frappe.db.get_value("Workspace", {"label": WORKSPACE_NAME}, "name")
		)
		ws = frappe.get_doc("Workspace", name)
		original_content = ws.content
		ws.content = '[{"id":"custom","type":"header","data":{"text":"Custom","col":12}}]'
		ws.flags.ignore_links = True
		ws.save(ignore_permissions=True)

		ensure_my_work()
		ws.reload()
		self.assertNotEqual(ws.content, original_content)
		self.assertIn("custom", ws.content or "")
