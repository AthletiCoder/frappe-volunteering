"""Native app session bootstrap must never grant or reveal more than the current session."""

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.mobile_session import get_mobile_session


class TestMobileSession(UnitTestCase):
	def test_guest_cannot_bootstrap(self):
		previous = frappe.session.user
		try:
			frappe.session.user = "Guest"
			with self.assertRaises(frappe.PermissionError):
				get_mobile_session()
		finally:
			frappe.session.user = previous

	def test_authenticated_bootstrap_only_returns_identity_and_csrf(self):
		previous = frappe.session.user
		try:
			frappe.session.user = "Administrator"
			with patch("volunteering.volunteering.mobile_session.get_csrf_token", return_value="test-csrf"):
				self.assertEqual(
					get_mobile_session(), {"user": "Administrator", "csrf_token": "test-csrf"}
				)
		finally:
			frappe.session.user = previous
