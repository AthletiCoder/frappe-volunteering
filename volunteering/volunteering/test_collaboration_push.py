"""Real membership/device/outbox tests; Google requests are mocked."""
import json
from unittest.mock import patch, Mock
from datetime import timedelta
import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime
from volunteering.volunteering import collaboration as c, collaboration_push as p
from volunteering.volunteering.collaboration_access import APP_ROLE, WEB_ROLE
from volunteering.volunteering.collaboration_setup import ensure_chat_role
from volunteering.volunteering.accounting_test_utils import get_or_create_user


class IntegrationTestCollaborationPush(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator"); ensure_chat_role()
		with patch("frappe.utils.global_search.sync_value_in_queue"):
			cls.people = [get_or_create_user(f"push-{name}@example.com", roles, first_name=name.title()) for name, roles in
				[("sender", [APP_ROLE, WEB_ROLE]), ("member", [APP_ROLE]), ("web", [WEB_ROLE]), ("outsider", [APP_ROLE])]]

	def setUp(self):
		super().setUp(); frappe.db.savepoint("push_case")
		self.owner, self.member, self.web, self.outsider = self.people
		self.config = {"enabled": True, "project_id": "sevamrita-tasks", "sender_id": "123456789", "apps": {
			"org.sevamrita.mobile": {"app_id": "1:123456789:android:example", "api_key": "public-api-key"}}}
		self.config_patch = patch.object(p, "_config", return_value=self.config); self.config_patch.start()
		self.enqueue_patch = patch("frappe.enqueue"); self.enqueue = self.enqueue_patch.start()
		frappe.set_user(self.owner)
		self.room = c.save_space({"title": "Push notification test", "members": [
			{"user": self.owner, "access_level": "Owner"}, {"user": self.member, "access_level": "Viewer"}, {"user": self.web, "access_level": "Member"}]})["name"]

	def tearDown(self):
		self.config_patch.stop(); self.enqueue_patch.stop()
		frappe.set_user("Administrator"); frappe.db.rollback(save_point="push_case")
		for user in self.people: frappe.clear_cache(user=user)
		super().tearDown()

	def register(self, user=None, installation="12345678-1234-1234-1234-123456789012", token="fcm-token-" + "x" * 40, binding="a" * 64):
		frappe.set_user(user or self.member)
		return p.register_device(installation, "org.sevamrita.mobile", token, binding)

	def message(self, key="first"):
		frappe.set_user(self.owner)
		return c.post_entry(self.room, "Hello everyone", request_key=key)["name"]

	def outbox(self, entry):
		return frappe.get_doc(p.OUTBOX, {"entry": entry})

	def test_public_config_never_returns_server_credentials(self):
		self.config["service_account"] = {"private_key": "secret"}
		result = p.get_push_config("org.sevamrita.mobile")
		self.assertTrue(result["enabled"])
		self.assertNotIn("secret", json.dumps(result)); self.assertNotIn("service_account", result)
		frappe.set_user(self.web)
		with self.assertRaises(frappe.PermissionError): p.get_push_config("org.sevamrita.mobile")

	def test_disabled_integration_is_a_noop(self):
		self.config["enabled"] = False
		self.assertFalse(p.get_push_config("org.sevamrita.mobile")["enabled"])
		entry = self.message()
		self.assertFalse(frappe.db.exists(p.OUTBOX, {"entry": entry}))

	def test_device_registration_is_idempotent_and_rotates_tokens(self):
		self.register(); self.register(token="new-token-" + "y" * 40)
		rows = frappe.get_all(p.DEVICE, filters={"user": self.member}, fields=["name", "enabled"])
		self.assertEqual(len(rows), 1); self.assertTrue(rows[0].enabled)
		doc = frappe.get_doc(p.DEVICE, rows[0].name)
		self.assertEqual(doc.get_password("token"), "new-token-" + "y" * 40)
		self.assertNotEqual(frappe.db.get_value(p.DEVICE, doc.name, "token"), doc.get_password("token"))

	def test_unregistration_can_only_disable_own_device(self):
		self.register()
		frappe.set_user(self.outsider)
		p.unregister_device("12345678-1234-1234-1234-123456789012", "org.sevamrita.mobile")
		self.assertEqual(frappe.db.count(p.DEVICE, {"user": self.member, "enabled": 1}), 1)
		frappe.set_user(self.member)
		p.unregister_device("12345678-1234-1234-1234-123456789012", "org.sevamrita.mobile")
		self.assertEqual(frappe.db.count(p.DEVICE, {"user": self.member, "enabled": 1}), 0)

	def test_sender_excluded_and_viewer_with_app_role_receives(self):
		self.register(); self.register(self.owner, installation="22345678-1234-1234-1234-123456789012", token="owner-token-" + "o" * 40)
		entry = self.message()
		box = self.outbox(entry)
		self.assertEqual(len(json.loads(box.recipients)), 1)
		with patch.object(p, "_send", return_value="sent") as send:
			p.deliver_outbox(box.name); self.assertEqual(send.call_args.args[0].user, self.member)
			p.deliver_outbox(box.name); self.assertEqual(send.call_count, 1)

	def test_removed_member_or_changed_session_does_not_receive_queued_push(self):
		self.register(); entry = self.message(); box = self.outbox(entry)
		self.register(binding="b" * 64)
		with patch.object(p, "_send") as send: p.deliver_outbox(box.name); send.assert_not_called()
		entry = self.message("second"); box = self.outbox(entry)
		room = frappe.get_doc("Collaboration Space", self.room)
		c.save_space({"members": [{"user": self.owner, "access_level": "Owner"}]}, self.room, str(room.modified))
		with patch.object(p, "_send") as send: p.deliver_outbox(box.name); send.assert_not_called()

	def test_new_members_do_not_receive_historical_queued_messages(self):
		self.register(); entry = self.message(); box = self.outbox(entry)
		self.register(self.outsider, installation="32345678-1234-1234-1234-123456789012", token="outsider-" + "z" * 40)
		frappe.set_user(self.owner); room = frappe.get_doc("Collaboration Space", self.room)
		c.save_space({"members": [{"user": self.owner, "access_level": "Owner"}, {"user": self.member, "access_level": "Viewer"},
			{"user": self.outsider, "access_level": "Member"}]}, self.room, str(room.modified))
		with patch.object(p, "_send", return_value="sent") as send:
			p.deliver_outbox(box.name); self.assertEqual([args.args[0].user for args in send.call_args_list], [self.member])

	def test_failed_send_retries_but_successful_device_is_not_repeated(self):
		self.register(); box = self.outbox(self.message())
		with patch.object(p, "_send", return_value="retry"): p.deliver_outbox(box.name)
		self.assertEqual(frappe.get_doc(p.OUTBOX, box.name).status, "Pending")
		with patch.object(p, "_send", return_value="sent"): p.deliver_outbox(box.name)
		self.assertEqual(frappe.get_doc(p.OUTBOX, box.name).status, "Sent")

	def test_unregistered_token_is_disabled(self):
		self.register(); box = self.outbox(self.message())
		with patch.object(p, "_send", return_value="invalid"): p.deliver_outbox(box.name)
		self.assertEqual(frappe.db.count(p.DEVICE, {"user": self.member, "enabled": 1}), 0)

	def test_notification_preview_rechecks_current_membership_and_read_state(self):
		entry = self.message(); frappe.set_user(self.member)
		self.assertTrue(p.get_notification_entry(entry)["notify"])
		from volunteering.volunteering import collaboration_mobile as app
		app.mark_seen(self.room, entry)
		self.assertFalse(p.get_notification_entry(entry)["notify"])
		frappe.set_user(self.outsider)
		self.assertFalse(p.get_notification_entry(entry)["notify"])

	def test_fcm_payload_contains_no_private_message_or_user_data(self):
		self.register(); box = self.outbox(self.message()); device = frappe.get_doc(p.DEVICE, json.loads(box.recipients)[0]["name"])
		entry = frappe.get_doc("Collaboration Entry", box.entry)
		with patch.object(p, "_access_token", return_value="oauth-token"), patch.object(p.requests, "post", return_value=Mock(status_code=200)) as post:
			self.assertEqual(p._send(device, entry), "sent")
			payload = post.call_args.kwargs["json"]["message"]
			self.assertEqual(set(payload["data"]), {"entry", "binding"})
			self.assertNotIn("Hello", json.dumps(payload)); self.assertNotIn(self.member, json.dumps(payload)); self.assertNotIn("notification", payload)

	def test_notification_schema_is_not_readable_or_writable_through_generic_api(self):
		self.register(); device = frappe.get_all(p.DEVICE, filters={"user": self.member}, pluck="name")[0]
		self.assertFalse(frappe.has_permission(p.DEVICE, "read", doc=device))
		with self.assertRaises(frappe.PermissionError):
			doc = frappe.get_doc(p.DEVICE, device); doc.enabled = 0; doc.save(ignore_permissions=True)

	def test_invalid_google_token_response_only_disables_unregistered_token(self):
		self.register(); box = self.outbox(self.message()); device = frappe.get_doc(p.DEVICE, json.loads(box.recipients)[0]["name"])
		entry = frappe.get_doc("Collaboration Entry", box.entry)
		for code, details, expected in [(404, [{"errorCode": "UNREGISTERED"}], "invalid"), (404, [], "retry"), (429, [], "retry"), (503, [], "retry")]:
			with patch.object(p, "_access_token", return_value="oauth-token"), patch.object(p.requests, "post", return_value=Mock(status_code=code, json=lambda: {"error": {"details": details}})):
				self.assertEqual(p._send(device, entry), expected)

	def test_retries_stop_and_do_not_send_deleted_or_expired_messages(self):
		self.register(); entry = self.message(); box = self.outbox(entry)
		with patch.object(p, "_send", return_value="retry"):
			for _ in range(6): p.deliver_outbox(box.name)
		self.assertEqual(frappe.get_doc(p.OUTBOX, box.name).status, "Failed")
		entry = self.message("old"); box = self.outbox(entry)
		frappe.db.set_value("Collaboration Entry", entry, "creation", now_datetime() - timedelta(days=2), update_modified=False)
		with patch.object(p, "_send") as send: p.deliver_outbox(box.name); send.assert_not_called()
		self.assertEqual(frappe.get_doc(p.OUTBOX, box.name).status, "Skipped")

	def test_large_device_audience_continues_without_repeating_successful_sends(self):
		for index in range(12):
			self.register(installation=f"{index:08d}-1234-1234-1234-123456789012", token=f"batch-token-{index}-" + "x" * 40)
		box = self.outbox(self.message())
		with patch.object(p, "_send", return_value="sent") as send:
			p.deliver_outbox(box.name)
			self.assertEqual(send.call_count, 10)
			self.assertEqual(len(json.loads(frappe.get_doc(p.OUTBOX, box.name).recipients)), 2)
			p.deliver_outbox(box.name)
			self.assertEqual(send.call_count, 12)
			self.assertEqual(frappe.get_doc(p.OUTBOX, box.name).status, "Sent")

	def test_oauth_assertion_uses_rsa_and_reuses_short_lived_access_token(self):
		import base64
		from cryptography.hazmat.primitives.asymmetric import rsa, padding
		from cryptography.hazmat.primitives import serialization, hashes
		key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
		self.config["service_account"] = {"project_id": "sevamrita-tasks", "client_email": "sender@sevamrita-tasks.iam.gserviceaccount.com",
			"private_key": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()}
		cache = Mock(); cache.get_value.return_value = None
		response = Mock(status_code=200, json=lambda: {"access_token": "short-lived-token"})
		with patch.object(frappe, "cache", cache), patch.object(p.requests, "post", return_value=response) as post:
			self.assertEqual(p._access_token(), "short-lived-token")
			parts = post.call_args.kwargs["data"]["assertion"].split(".")
			decode = lambda value: base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
			claims = json.loads(decode(parts[1]))
			self.assertEqual(claims["aud"], "https://oauth2.googleapis.com/token")
			self.assertEqual(claims["scope"], "https://www.googleapis.com/auth/firebase.messaging")
			key.public_key().verify(decode(parts[2]), ".".join(parts[:2]).encode(), padding.PKCS1v15(), hashes.SHA256())
			cache.get_value.return_value = "short-lived-token"
			self.assertEqual(p._access_token(), "short-lived-token"); self.assertEqual(post.call_count, 1)

	def test_setup_rejects_mismatched_projects_and_packages(self):
		from volunteering.volunteering.collaboration_push_setup import firebase_config
		from cryptography.hazmat.primitives.asymmetric import rsa
		from cryptography.hazmat.primitives import serialization
		key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
		account = {"type": "service_account", "project_id": "sevamrita-tasks", "client_email": "sender@sevamrita-tasks.iam.gserviceaccount.com",
			"private_key": key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()}
		client = {"project_info": {"project_id": "sevamrita-tasks", "project_number": "123456789"}, "client": [{
			"client_info": {"android_client_info": {"package_name": "org.sevamrita.mobile"}, "mobilesdk_app_id": "1:123456789:android:example"},
			"api_key": [{"current_key": "public-api-key"}]}]}
		self.assertTrue(firebase_config(account, {"org.sevamrita.mobile": client})["enabled"])
		with self.assertRaises(ValueError): firebase_config(account, {"org.sevamrita.mobile.local": client})
		with self.assertRaises(ValueError): firebase_config(account | {"project_id": "another-project"}, {"org.sevamrita.mobile": client})

	def test_mention_preview_flags_and_system_assignment_alerts_are_targeted(self):
		self.register()
		entry=self.message('plain-preview')
		frappe.set_user(self.member)
		self.assertFalse(p.get_notification_entry(entry)['mentioned'])
		frappe.set_user(self.owner)
		entry=c.post_entry(self.room,f'@[Member]({self.member}) please check',request_key='mention-preview')['name']
		frappe.set_user(self.member)
		self.assertTrue(p.get_notification_entry(entry)['mentioned'])
		self.assertEqual(p.get_notification_entry(entry)['body'],'@Member please check')
		frappe.set_user(self.owner)
		entry=c._entry(self.room,'Assigned task: kitchen delivery',snapshot={'notify_users':[self.member]})
		self.assertTrue(frappe.db.exists(p.OUTBOX,{'entry':entry.name}))
		frappe.set_user(self.member)
		self.assertTrue(p.get_notification_entry(entry.name)['assigned'])
		frappe.set_user(self.web)
		with self.assertRaises(frappe.PermissionError): p.get_notification_entry(entry.name)
