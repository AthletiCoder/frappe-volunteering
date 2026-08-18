# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.desk_icons_setup import ensure_desk_icons
from volunteering.volunteering.home_service import (
	ADVANCES_URL,
	BUDGET_HEALTH_URL,
	HOME_URL,
	TODOS_URL,
)


class IntegrationTestDeskIcons(IntegrationTestCase):
	def test_desk_icons_open_spa_pages(self):
		if not frappe.db.exists("DocType", "Desktop Icon"):
			self.skipTest("Desktop Icon is not installed")

		ensure_desk_icons()
		expected = {
			"Home": HOME_URL,
			"To-do": TODOS_URL,
			"Advance Portal": ADVANCES_URL,
			"Budget Health": BUDGET_HEALTH_URL,
		}
		for label, url in expected.items():
			self.assertTrue(frappe.db.exists("Desktop Icon", label), label)
			doc = frappe.get_doc("Desktop Icon", label)
			self.assertEqual(doc.link, url)
			self.assertEqual(doc.hidden, 0)
			self.assertEqual(doc.link_type, "External")
