"""The metadata compatibility fix must not commit or roll back application work."""

from unittest.mock import Mock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.login_session import _update_metadata, install_session_metadata_isolation


class TestLoginSession(UnitTestCase):
	def test_hooks_cover_new_and_resumed_sessions(self):
		method = "volunteering.volunteering.login_session.install_session_metadata_isolation"
		self.assertIn(method, frappe.get_hooks("on_login"))
		self.assertIn(method, frappe.get_hooks("before_request"))

	def test_installation_is_idempotent_and_guest_does_not_open_connection(self):
		import frappe.sessions

		def original(user, **values):
			pass

		with patch.object(frappe.sessions, "update_user_metadata", original):
			install_session_metadata_isolation()
			installed = frappe.sessions.update_user_metadata
			install_session_metadata_isolation()
			self.assertIs(installed, frappe.sessions.update_user_metadata)
			with patch("volunteering.volunteering.login_session.get_db") as database:
				installed("Guest", last_active="2026-10-27")
				installed("employee@example.com")
				database.assert_not_called()

	def test_metadata_uses_separate_commit_and_restores_request_database(self):
		request_db = frappe.local.db
		metadata_db = Mock()
		values = {"last_login": "2026-10-27 12:00:00", "run_notifications": True}

		def original(user, **received):
			self.assertIs(frappe.local.db, metadata_db)
			self.assertEqual(user, "employee@example.com")
			self.assertEqual(received, values)

		with patch("volunteering.volunteering.login_session.get_db", return_value=metadata_db):
			with patch.object(request_db, "commit") as commit, patch.object(request_db, "rollback") as rollback:
				_update_metadata(original, "employee@example.com", values)
				commit.assert_not_called()
				rollback.assert_not_called()
		self.assertIs(frappe.local.db, request_db)
		metadata_db.get_value.assert_called_once_with("User", "employee@example.com", "name", for_update=True, wait=False)
		metadata_db.commit.assert_called_once()
		metadata_db.rollback.assert_not_called()
		metadata_db.close.assert_called_once()

	def test_deadlock_or_lost_savepoint_does_not_rollback_request(self):
		request_db = frappe.local.db
		for error in (frappe.QueryDeadlockError("conflict"), RuntimeError("SAVEPOINT no longer exists")):
			with self.subTest(error=type(error).__name__):
				metadata_db = Mock()
				with patch("volunteering.volunteering.login_session.get_db", return_value=metadata_db):
					with patch.object(request_db, "commit") as commit, patch.object(request_db, "rollback") as rollback:
						with patch.object(frappe, "logger"):
							_update_metadata(Mock(side_effect=error), "employee@example.com", {"last_active": "now"})
						commit.assert_not_called()
						rollback.assert_not_called()
				self.assertIs(frappe.local.db, request_db)
				metadata_db.commit.assert_not_called()
				metadata_db.rollback.assert_called_once()
				metadata_db.close.assert_called_once()

	def test_connection_or_cleanup_failure_restores_request_database(self):
		request_db = frappe.local.db
		with patch("volunteering.volunteering.login_session.get_db", side_effect=RuntimeError("offline")):
			with patch.object(frappe, "logger"):
				_update_metadata(Mock(), "employee@example.com", {"last_active": "now"})
		self.assertIs(frappe.local.db, request_db)
		metadata_db = Mock()
		metadata_db.rollback.side_effect = RuntimeError("already rolled back")
		metadata_db.close.side_effect = RuntimeError("already closed")
		with patch("volunteering.volunteering.login_session.get_db", return_value=metadata_db):
			with patch.object(frappe, "logger"):
				_update_metadata(Mock(side_effect=RuntimeError("conflict")), "employee@example.com", {"last_active": "now"})
		self.assertIs(frappe.local.db, request_db)

	def test_busy_user_skips_metadata_without_waiting(self):
		request_db = frappe.local.db
		metadata_db = Mock()
		metadata_db.get_value.side_effect = frappe.QueryTimeoutError("row busy")
		original = Mock()
		with patch("volunteering.volunteering.login_session.get_db", return_value=metadata_db):
			with patch.object(frappe, "logger"):
				_update_metadata(original, "employee@example.com", {"last_active": "now"})
		original.assert_not_called()
		metadata_db.commit.assert_not_called()
		self.assertIs(frappe.local.db, request_db)


class IntegrationTestLoginSession(IntegrationTestCase):
	def test_metadata_does_not_wait_on_or_commit_the_callers_user_edit(self):
		request_db = frappe.local.db
		# A login hook can legitimately edit the User in its current transaction.
		# The separate metadata connection must skip this locked row, not wait
		# for the very transaction whose login is waiting for it to finish.
		frappe.db.get_value("User", "Administrator", "name", for_update=True)
		original = Mock()
		with patch.object(request_db, "commit") as commit, patch.object(request_db, "rollback") as rollback:
			with patch.object(frappe, "logger"):
				_update_metadata(original, "Administrator", {"last_active": "2026-10-27 12:00:00"})
			commit.assert_not_called()
			rollback.assert_not_called()
		original.assert_not_called()
		self.assertIs(frappe.local.db, request_db)
