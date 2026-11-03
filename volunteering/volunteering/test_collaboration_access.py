"""Regression checks for independent web and native chat access."""
from unittest.mock import patch
import frappe
from frappe.tests import IntegrationTestCase
from volunteering.volunteering import collaboration as web, collaboration_mobile as app
from volunteering.volunteering.collaboration_access import APP_ROLE, WEB_ROLE, LEGACY_ROLE, chat_channel
from volunteering.volunteering.collaboration_setup import ensure_chat_role
from volunteering.volunteering.accounting_test_utils import get_or_create_user


class IntegrationTestChatInterfaceAccess(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		ensure_chat_role()
		with patch("frappe.utils.global_search.sync_value_in_queue"):
			cls.web_user = get_or_create_user("chat-web-only@example.com", [WEB_ROLE], first_name="Web")
			cls.app_user = get_or_create_user("chat-app-only@example.com", [APP_ROLE], first_name="App")
			cls.both_user = get_or_create_user("chat-both@example.com", [WEB_ROLE, APP_ROLE], first_name="Both")
			cls.neither = get_or_create_user("chat-neither@example.com", ["Employee"], first_name="Neither")

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("chat_interface_case")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="chat_interface_case")
		for user in (self.web_user, self.app_user, self.both_user, self.neither):
			frappe.clear_cache(user=user)
		super().tearDown()

	def test_role_matrix_for_read_write_and_reminders(self):
		for user, allow_web, allow_app in [(self.web_user, True, False), (self.app_user, False, True),
			(self.both_user, True, True), (self.neither, False, False), ("Guest", False, False)]:
			frappe.set_user(user)
			for api, allowed in [(web, allow_web), (app, allow_app)]:
				with self.subTest(user=user, api=api.__name__):
					if allowed:
						self.assertEqual(api.get_collaboration_home()["user"], user)
						api.save_space({"title": "Role matrix chat"})
					else:
						for call in [api.get_collaboration_home, lambda: api.save_space({"title": "Denied"})]:
							with self.assertRaises(frappe.PermissionError): call()
			if allow_app:
				self.assertEqual(app.get_reminders()["user"], user)
			else:
				with self.assertRaises(frappe.PermissionError): app.get_reminders()
			self.assertEqual(chat_channel.get(), "web")

	def test_cross_interface_participants_share_the_same_chat(self):
		frappe.set_user(self.web_user)
		room = web.save_space({"title": "Shared ERP data", "members": [
			{"user": self.web_user, "access_level": "Owner"}, {"user": self.app_user, "access_level": "Member"}]})["name"]
		self.assertIn(self.app_user, [p.name for p in web.get_directory()])
		frappe.set_user(self.app_user)
		entry = app.post_entry(room, "Sent from app", request_key="native-role-check")
		frappe.set_user(self.web_user)
		self.assertIn(entry["name"], [row["name"] for row in web.get_space(room)["entries"]])

	def test_app_role_does_not_change_erp_home(self):
		from volunteering.volunteering.home_service import get_home_payload
		for user, expected in [(self.app_user, False), (self.web_user, True), (self.both_user, True), (self.neither, False)]:
			frappe.set_user(user)
			payload = get_home_payload()
			self.assertEqual(payload["flags"]["show_chat"], expected)
			self.assertEqual(bool(payload["actions"].get("collaboration")), expected)
			if not expected:
				self.assertFalse(any(row.get("route", "").startswith("/volunteering/collaboration") for row in payload["waiting"]))

	def test_native_context_cannot_leak_after_exception(self):
		frappe.set_user(self.app_user)
		with self.assertRaises(frappe.PermissionError): app.get_space("nonexistent-space")
		self.assertEqual(chat_channel.get(), "web")
		with self.assertRaises(frappe.PermissionError): web.get_collaboration_home()

	def test_legacy_role_migration_preserves_app_only_and_is_idempotent(self):
		frappe.set_user("Administrator")
		if not frappe.db.exists("Role", LEGACY_ROLE):
			frappe.get_doc({"doctype": "Role", "role_name": LEGACY_ROLE, "desk_access": 0}).insert(ignore_permissions=True)
		frappe.db.set_value("Role", LEGACY_ROLE, "disabled", 0, update_modified=False)
		user = frappe.get_doc("User", self.neither)
		user.append("roles", {"role": LEGACY_ROLE})
		user.flags.no_welcome_mail = True
		user.save(ignore_permissions=True)
		ensure_chat_role()
		ensure_chat_role()
		roles = [row.role for row in frappe.get_doc("User", self.neither).roles]
		self.assertEqual(roles.count(APP_ROLE), 1)
		self.assertNotIn(WEB_ROLE, roles)
		self.assertNotIn(LEGACY_ROLE, roles)

	def test_native_api_exposes_the_same_explicit_method_signatures(self):
		import inspect
		for name, method in inspect.getmembers(web, inspect.isfunction):
			if method not in frappe.whitelisted:
				continue
			self.assertTrue(hasattr(app, name), name)
			self.assertEqual(inspect.signature(getattr(app, name)), inspect.signature(method), name)

	def test_migration_normalizes_roles_auto_created_by_doctype_sync(self):
		frappe.set_user("Administrator")
		for role in (WEB_ROLE, APP_ROLE):
			frappe.db.set_value("Role", role, "desk_access", 1, update_modified=False)
		ensure_chat_role()
		for role in (WEB_ROLE, APP_ROLE):
			self.assertFalse(frappe.db.get_value("Role", role, "desk_access"))

	def test_disabled_role_blocks_only_its_interface(self):
		for role, denied, allowed in [(APP_ROLE, app, web), (WEB_ROLE, web, app)]:
			frappe.set_user("Administrator")
			frappe.db.set_value("Role", role, "disabled", 1, update_modified=False)
			frappe.set_user(self.both_user)
			with self.assertRaises(frappe.PermissionError): denied.get_collaboration_home()
			self.assertEqual(allowed.get_collaboration_home()["user"], self.both_user)
			frappe.set_user("Administrator")
			frappe.db.set_value("Role", role, "disabled", 0, update_modified=False)
