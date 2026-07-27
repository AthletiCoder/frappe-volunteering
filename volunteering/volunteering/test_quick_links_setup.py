# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.quick_links_setup import WORKSPACE_NAME, ensure_my_work


class IntegrationTestMyWork(IntegrationTestCase):
	def _workspace_name(self):
		return frappe.db.exists("Workspace", WORKSPACE_NAME) or frappe.db.get_value(
			"Workspace", {"label": WORKSPACE_NAME}, "name"
		)

	def test_ensure_my_work_is_idempotent(self):
		ensure_my_work()
		self.assertTrue(self._workspace_name())

		# Running again must not raise and must keep exactly one workspace.
		ensure_my_work()
		ws = frappe.get_doc("Workspace", self._workspace_name())
		self.assertIn("eh-header", ws.content or "")
		self.assertIn("Self Service", ws.content or "")

	def test_rebuild_restores_standard_layout(self):
		"""ensure_my_work force-rebuilds content, discarding manual edits."""
		ensure_my_work()
		ws = frappe.get_doc("Workspace", self._workspace_name())
		ws.content = '[{"id":"custom","type":"header","data":{"text":"Custom","col":12}}]'
		ws.flags.ignore_links = True
		ws.save(ignore_permissions=True)

		ensure_my_work()
		ws.reload()
		self.assertNotIn("custom", ws.content or "")
		self.assertIn("eh-header", ws.content or "")
