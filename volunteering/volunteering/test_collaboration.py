"""Exercise real collaboration records and permission hooks without emails or external services."""
import base64
from datetime import timedelta
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_days, get_datetime, now_datetime, nowdate

from volunteering.volunteering import collaboration as c
from volunteering.volunteering.collaboration_setup import ensure_chat_role
from volunteering.volunteering.accounting_test_utils import get_or_create_user


class IntegrationTestCollaboration(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		ensure_chat_role()
		with patch("frappe.utils.global_search.sync_value_in_queue"):
			cls.users = [get_or_create_user(f"collab-{name}@example.com", list(c.CHAT_ROLES), first_name=name.title())
				for name in ("owner", "member", "viewer", "manager", "outsider")]
			cls.no_role = get_or_create_user("collab-no-role@example.com", ["Employee"], first_name="Nochat")

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("collaboration_case")
		self.owner, self.member, self.viewer, self.manager, self.outsider = self.users
		frappe.set_user(self.owner)
		self.room = c.save_space({"title": "Kitchen service planning", "space_kind": "Workspace", "members": [
			{"user": uid, "access_level": level} for uid, level in zip(self.users[:4], ["Owner", "Member", "Viewer", "Manager"])]})["name"]

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="collaboration_case")
		# User.save updates the role cache outside the database savepoint.
		for user in self.users:
			frappe.clear_cache(user=user)
		super().tearDown()

	def task(self, **values):
		return c.save_item(self.room, {"item_kind": "Task", "title": "Buy utensils", **values})

	def tracker(self, **config):
		return c.save_item(self.room, {"item_kind": "Tracker", "title": "Meals served", "assignee": self.owner,
			"item_data": {"scale": "Percentage", **config}})

	def test_role_required_for_home_and_known_links(self):
		for uid in [self.no_role, "Guest", "Administrator"]:
			frappe.set_user(uid)
			if uid == "Administrator" and c.has_chat_access():
				continue
			self.assertFalse(c.has_chat_access())
			for method, args in [(c.get_collaboration_home, {}), (c.get_space, {"name": self.room}),
				(c.get_my_work, {}), (c.post_entry, {"space": self.room, "body": "Blocked", "request_key": "denied"})]:
				with self.subTest(user=uid, method=method.__name__), self.assertRaises(frappe.PermissionError):
					method(**args)

	def test_membership_required_even_with_role(self):
		frappe.set_user(self.outsider)
		self.assertNotIn(self.room, [r["name"] for r in c.get_collaboration_home()["spaces"]])
		with self.assertRaises(frappe.PermissionError):
			c.get_space(self.room)

	def test_viewer_reads_but_cannot_write(self):
		frappe.set_user(self.viewer)
		self.assertFalse(c.get_space(self.room)["space"]["can_post"])
		for method, args in [(c.post_entry, {"space": self.room, "body": "No", "request_key": "viewer"}),
			(c.save_item, {"space": self.room, "payload": {"item_kind": "Task", "title": "No"}})]:
			with self.assertRaises(frappe.PermissionError):
				method(**args)

	def test_area_inherits_and_cannot_move_outside_workspace(self):
		area = c.save_space({"title": "Food distribution", "parent_space": self.room})["name"]
		frappe.set_user(self.member)
		self.assertEqual(c.get_space(area)["space"]["access_level"], "Member")
		c.post_entry(area, "Route confirmed", request_key="inherited")
		with self.assertRaises(frappe.PermissionError):
			c.save_space({"title": "Forbidden area", "parent_space": area})
		frappe.set_user(self.owner)
		other = c.save_space({"title": "Other workspace"})["name"]
		with self.assertRaises(frappe.ValidationError):
			c.save_space({"parent_space": other}, area, c.get_space(area)["space"]["modified"])

	def test_manager_cannot_promote_or_remove_owner(self):
		frappe.set_user(self.manager)
		room = c.get_space(self.room)["space"]
		with self.assertRaises(frappe.PermissionError):
			c.save_space({"members": [{"user": self.manager, "access_level": "Owner"}]}, self.room, room["modified"])

	def test_owner_cannot_remove_every_owner(self):
		with self.assertRaises(frappe.ValidationError):
			c.save_space({"members": [{"user": self.owner, "access_level": "Member"}]}, self.room,
				c.get_space(self.room)["space"]["modified"])

	def test_stale_space_update_rejected(self):
		stamp = c.get_space(self.room)["space"]["modified"]
		c.save_space({"title": "Updated title"}, self.room, stamp)
		with self.assertRaises(frappe.ValidationError):
			c.save_space({"title": "Lost update"}, self.room, stamp)

	def test_archive_blocks_writes_and_can_be_reopened(self):
		c.save_space({"archived": 1}, self.room, c.get_space(self.room)["space"]["modified"])
		with self.assertRaises(frappe.PermissionError):
			self.task()
		c.save_space({"archived": 0}, self.room, c.get_space(self.room)["space"]["modified"])
		self.task()

	def test_direct_reused_from_either_participant(self):
		first = c.start_direct(self.member)["name"]
		frappe.set_user(self.member)
		self.assertEqual(first, c.start_direct(self.owner)["name"])
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			c.get_space(first)

	def test_directory_excludes_users_without_role(self):
		self.assertNotIn(self.no_role, [u.name for u in c.get_directory()])
		with self.assertRaises(frappe.ValidationError):
			c.start_direct(self.no_role)

	def test_message_retry_deduplication_and_conflict(self):
		one = c.post_entry(self.room, "Check the delivery", request_key="same")
		self.assertEqual(one, c.post_entry(self.room, "Check the delivery", request_key="same"))
		with self.assertRaises(frappe.ValidationError):
			c.post_entry(self.room, "Different message", request_key="same")

	def test_cross_space_message_links_rejected(self):
		other = c.save_space({"title": "Other"})["name"]
		message = c.post_entry(other, "Private note", request_key="source")["name"]
		with self.assertRaises(frappe.ValidationError):
			self.task(source_entry=message)

	def test_member_cannot_edit_another_members_message(self):
		message = c.post_entry(self.room, "Owner note", request_key="note")["name"]
		stamp = frappe.get_doc(c.PREFIX + "Entry", message).modified
		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			c.edit_entry(message, "Changed", expected_modified=str(stamp))

	def test_removed_message_is_tombstone_and_linked_task_remains(self):
		message = c.post_entry(self.room, "Original", request_key="remove")["name"]
		task = self.task(source_entry=message)
		c.edit_entry(message, remove=True, expected_modified=str(frappe.get_doc(c.PREFIX + "Entry", message).modified))
		entry = next(e for e in c.get_space(self.room)["entries"] if e["name"] == message)
		self.assertEqual(entry["body"], "Message removed")
		self.assertTrue(frappe.db.exists(c.PREFIX + "Item", task["name"]))

	def test_only_author_can_edit_and_moderator_can_remove(self):
		original = c.post_entry(self.room, "Original", request_key="original")["name"]
		name = c.post_entry(self.room, "Typo", request_key="typo", source_entry=original)["name"]
		before = c.get_space(self.room)["entries"][-1]
		c.edit_entry(name, "Corrected", expected_modified=before["modified"])
		after = c.get_space(self.room)["entries"][-1]
		self.assertEqual(after["body"], "Corrected")
		self.assertEqual(after["creation"], before["creation"])
		self.assertEqual(after["source_entry"], original)
		self.assertTrue(after["edited_at"])
		with self.assertRaises(frappe.ValidationError):
			c.edit_entry(name, "Stale edit", expected_modified=before["modified"])
		frappe.set_user(self.manager)
		moderation = c.get_space(self.room)["entries"][-1]
		self.assertFalse(moderation["can_edit"])
		self.assertTrue(moderation["can_remove"])
		with self.assertRaises(frappe.PermissionError):
			c.edit_entry(name, "Impersonation", expected_modified=after["modified"])
		c.edit_entry(name, remove=True, expected_modified=after["modified"])
		frappe.set_user(self.owner)
		with self.assertRaises(frappe.PermissionError):
			c.edit_entry(name, "Restore", expected_modified=c.get_space(self.room)["entries"][-1]["modified"])

	def test_receipts_distinguish_delivery_read_and_legacy_unread_markers(self):
		from volunteering.volunteering import collaboration_mobile as mobile

		first = c.post_entry(self.room, "One", request_key="receipt-one")["name"]
		second = c.post_entry(self.room, "Two", request_key="receipt-two")["name"]
		frappe.set_user(self.member)
		c.get_space(self.room)
		c.mark_read(self.room, second)  # Old clients update unread counts only.
		mobile.mark_delivered(self.room, second)
		mobile.mark_delivered(self.room, first)
		with self.assertRaises(frappe.PermissionError):
			mobile.get_message_info(second)
		frappe.set_user(self.viewer)
		mobile.mark_seen(self.room, first)
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			mobile.mark_seen(self.room, second)
		with self.assertRaises(frappe.PermissionError):
			mobile.get_message_info(first)
		frappe.set_user(self.owner)
		self.assertEqual({row["user"]: row["status"] for row in mobile.get_message_info(first)["recipients"]},
			{self.member: 2, self.viewer: 3, self.manager: 1})
		self.assertEqual({row["user"]: row["status"] for row in mobile.get_message_info(second)["recipients"]},
			{self.member: 2, self.viewer: 1, self.manager: 1})
		self.assertEqual(mobile.get_space(self.room)["receipt_through"], {"delivered_through": "", "seen_through": ""})
		for user in (self.member, self.viewer, self.manager):
			frappe.set_user(user)
			mobile.mark_seen(self.room, second)
			mobile.mark_seen(self.room, first)
		frappe.set_user(self.owner)
		room = mobile.get_space(self.room)
		self.assertEqual(room["receipt_through"], dict.fromkeys(("delivered_through", "seen_through"),
			room["entries"][-1]["creation"]))

	def test_current_progress_is_latest_effective_snapshot_with_tie_break(self):
		tracker = self.tracker()
		current = now_datetime() - timedelta(hours=1)
		for value, stamp in ((20, current), (40, current), (5, current - timedelta(minutes=1))):
			tracker = c.record_progress(tracker["name"], tracker["modified"], f"At {value}", value=value, effective_at=stamp)
		room = c.get_space(self.room)
		entries = [entry for entry in room["entries"] if entry["entry_kind"] == "Progress"]
		self.assertEqual([entry["snapshot"]["item_data"]["value"] for entry in entries], [20, 40, 5])
		self.assertEqual(room["current_progress"][tracker["name"]], entries[1]["name"])
		self.assertEqual(c.get_space(self.room, before=entries[-1]["name"])["current_progress"], room["current_progress"])

	def test_progress_snapshots_keep_the_person_responsible_after_reassignment(self):
		tracker = self.tracker()
		tracker = c.record_progress(tracker["name"], tracker["modified"], "Initial update", value=20)
		c.save_item(self.room, {"assignee": self.member}, tracker["name"], tracker["modified"])
		entry = next(row for row in c.get_space(self.room)["entries"] if row["entry_kind"] == "Progress")
		self.assertEqual(entry["snapshot"]["pending_with"], {
			"user": self.owner, "full_name": frappe.db.get_value("User", self.owner, "full_name")})

	def test_progress_snapshots_record_the_stage_assignee_and_clear_it_when_complete(self):
		tracker = self.tracker(scale="Status", assignment_mode="Stages", stages=[
			{"key": "prepare", "label": "Prepare", "assignee": self.owner},
			{"key": "review", "label": "Review", "assignee": self.member}])
		tracker = c.record_progress(tracker["name"], tracker["modified"], "Before starting")
		tracker = c.record_progress(tracker["name"], tracker["modified"], "For review", stage="review")
		c.record_progress(tracker["name"], tracker["modified"], "Finished", outcome="Completed")
		updates = {row["body"]: row["snapshot"]["pending_with"] for row in c.get_space(self.room)["entries"]
			if row["entry_kind"] == "Progress"}
		self.assertEqual(updates["Before starting"]["user"], self.owner)
		self.assertEqual(updates["For review"]["user"], self.member)
		self.assertIsNone(updates["Finished"])

	def test_read_marker_monotonic_and_viewer_allowed(self):
		one = c.post_entry(self.room, "One", request_key="one")["name"]
		two = c.post_entry(self.room, "Two", request_key="two")["name"]
		frappe.set_user(self.viewer)
		c.mark_read(self.room, two)
		c.mark_read(self.room, one)
		stamp = frappe.db.get_value(c.PREFIX + "Read State", {"space": self.room, "user": self.viewer}, "read_at")
		self.assertEqual(stamp, frappe.db.get_value(c.PREFIX + "Entry", two, "creation"))

	def test_direct_document_writes_blocked(self):
		doc = frappe.get_doc(c.PREFIX + "Space", self.room)
		doc.title = "Bypass"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_query_permissions_hide_other_workspaces(self):
		frappe.set_user(self.outsider)
		self.assertEqual(frappe.get_list(c.PREFIX + "Space", filters={"name": self.room}, pluck="name"), [])

	def test_assignee_must_be_eligible_member(self):
		for uid in [self.no_role, self.outsider, self.viewer]:
			with self.subTest(user=uid), self.assertRaises(frappe.ValidationError):
				self.task(assignee=uid)

	def test_assignee_can_complete_but_other_member_cannot(self):
		task = self.task(assignee=self.member)
		frappe.set_user(self.viewer)
		with self.assertRaises(frappe.PermissionError):
			c.update_task(task["name"], "complete", task["modified"])
		frappe.set_user(self.member)
		self.assertEqual(c.update_task(task["name"], "complete", task["modified"])["status"], "Completed")

	def test_task_window_snooze_postpone_and_deadline(self):
		today = nowdate()
		task = self.task(from_date=today, until_date=add_days(today, 4), deadline=add_days(today, 7))
		task = c.update_task(task["name"], "snooze", task["modified"], add_days(today, 2))
		self.assertNotIn(task["name"], [i["name"] for i in c.get_my_work()["today"]])
		task = c.update_task(task["name"], "postpone", task["modified"], add_days(today, 3))
		self.assertEqual(str(task["until_date"]), str(add_days(today, 7)))
		self.assertEqual(str(task["deadline"]), str(add_days(today, 7)))
		self.assertFalse(task["snoozed_until"])

	def test_assignee_can_start_task_and_it_stays_in_open_work(self):
		task = self.task(assignee=self.member, from_date=nowdate(), repeat_pattern="Daily")
		frappe.set_user(self.member)
		started = c.update_task(task["name"], "start", task["modified"])
		self.assertEqual(started["status"], "In progress")
		self.assertIn(task["name"], [i["name"] for i in c.get_my_work()["today"]])
		series = frappe.db.get_value(c.PREFIX + "Item", task["name"], "series_key")
		self.assertEqual(frappe.db.count(c.PREFIX + "Item", {"series_key": series}), 1)
		completed = c.update_task(task["name"], "complete", started["modified"])
		self.assertEqual(completed["status"], "Completed")
		self.assertEqual(frappe.db.count(c.PREFIX + "Item", {"series_key": series}), 2)

	def test_start_requires_edit_permission_and_current_version(self):
		task = self.task(assignee=self.member)
		for user in [self.viewer, self.outsider]:
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				c.update_task(task["name"], "start", task["modified"])
		frappe.set_user(self.member)
		started = c.update_task(task["name"], "start", task["modified"])
		with self.assertRaises(frappe.ValidationError):
			c.update_task(task["name"], "reopen", task["modified"])
		self.assertEqual(c.update_task(task["name"], "reopen", started["modified"])["status"], "Open")

	def test_personal_tracker_filters_can_include_completed_without_leaking_other_users(self):
		tracker = self.tracker()
		completed = c.record_progress(tracker["name"], tracker["modified"], "Finished", value=100, outcome="Completed")
		work = c.get_my_work()
		self.assertIn(completed["name"], [i["name"] for i in work["trackers"]])
		self.assertNotIn(completed["name"], [i["name"] for i in work["open_progress"]])
		frappe.set_user(self.member)
		self.assertNotIn(completed["name"], [i["name"] for i in c.get_my_work()["trackers"]])
		frappe.set_user(self.outsider)
		self.assertNotIn(completed["name"], [i["name"] for i in c.get_my_work()["trackers"]])

	def test_direct_tracker_link_loads_older_item_and_keeps_room_scope(self):
		tracker = self.tracker()
		real_get_all = frappe.get_all
		def initial_list_excludes_older_item(doctype, *args, **kwargs):
			if doctype == c.PREFIX + "Item" and kwargs.get("limit_page_length") == 300:
				return []
			return real_get_all(doctype, *args, **kwargs)
		with patch.object(frappe, "get_all", side_effect=initial_list_excludes_older_item):
			self.assertIn(tracker["name"], [i["name"] for i in c.get_space(self.room, item=tracker["name"])["items"]])
		other = c.save_space({"title": "Separate private room"})["name"]
		with self.assertRaises(frappe.PermissionError):
			c.get_space(other, item=tracker["name"])
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			c.get_space(self.room, item=tracker["name"])

	def test_stage_assignment_requires_each_contributing_chat_member(self):
		config = {"scale": "Stages", "assignment_mode": "Stages", "stages": [
			{"key": "plan", "label": "Plan", "position": 40, "assignee": self.owner},
			{"key": "serve", "label": "Serve", "position": 100, "assignee": self.member}]}
		tracker = self.tracker(**config)
		self.assertFalse(tracker["assignee"])
		self.assertEqual(tracker["item_data"]["stages"][1]["assignee_name"], c._name(self.member))
		frappe.set_user(self.member)
		self.assertIn(tracker["name"], [r["name"] for r in c.get_my_work()["trackers"]])
		frappe.set_user(self.owner)
		for invalid in [None, self.viewer, self.outsider]:
			broken = {**config, "stages": [{**config["stages"][0], "assignee": invalid}]}
			with self.assertRaises(frappe.ValidationError):
				self.tracker(**broken)

	def test_creator_sees_tracker_assigned_to_someone_else(self):
		tracker = c.save_item(self.room, {"item_kind": "Tracker", "title": "Delegated", "assignee": self.member, "item_data": {"scale": "Percentage"}})
		self.assertIn(tracker["name"], [r["name"] for r in c.get_my_work()["trackers"]])

	def test_shared_view_does_not_share_chat_or_allow_updates(self):
		task = self.task()
		task = c.share_item(task["name"], [{"user": self.outsider}], task["modified"])
		frappe.set_user(self.outsider)
		shared = c.get_work_item(task["name"])
		self.assertFalse(shared["space"]["can_post"])
		self.assertFalse(shared["items"][0]["can_update"])
		self.assertFalse(shared["entries"])
		self.assertIn(task["name"], [r["name"] for r in c.get_my_work()["open_progress"]])
		self.assertEqual(frappe.get_list(c.PREFIX + "Item", filters={"name": task["name"]}, pluck="name"), [task["name"]])
		c.get_item_history(task["name"])
		with self.assertRaises(frappe.PermissionError):
			c.get_space(self.room)
		with self.assertRaises(frappe.PermissionError):
			c.update_task(task["name"], "start", task["modified"])

	def test_shared_update_can_progress_but_cannot_reshare_or_configure(self):
		tracker = self.tracker()
		tracker = c.share_item(tracker["name"], [{"user": self.outsider, "access": "Update"}], tracker["modified"])
		frappe.set_user(self.outsider)
		updated = c.record_progress(tracker["name"], tracker["modified"], "Contributed", value=50)
		self.assertEqual(updated["item_data"]["value"], 50)
		self.assertFalse(updated["can_share"])
		with self.assertRaises(frappe.PermissionError):
			c.share_item(tracker["name"], [], updated["modified"])
		with self.assertRaises(frappe.PermissionError):
			c.save_item(self.room, {"title": "Hijacked"}, tracker["name"], updated["modified"])

	def test_sharing_revocation_and_role_revocation_take_effect_immediately(self):
		task = self.task()
		task = c.share_item(task["name"], [{"user": self.outsider, "access": "Update"}], task["modified"])
		frappe.set_user(self.outsider)
		task = c.update_task(task["name"], "start", task["modified"])
		frappe.set_user(self.owner)
		c.share_item(task["name"], [], task["modified"])
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError):
			c.get_work_item(task["name"])
		self.assertNotIn(task["name"], c._shared_ids())
		frappe.set_user(self.owner)
		with self.assertRaises(frappe.ValidationError):
			c.share_item(task["name"], [{"user": self.no_role}], str(frappe.get_doc(c.PREFIX + "Item", task["name"]).modified))

	def test_member_assignee_cannot_share_someone_elses_task(self):
		task = self.task(assignee=self.member)
		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			c.share_item(task["name"], [{"user": self.outsider}], task["modified"])

	def test_timed_reminders_use_portal_timezone_and_stop_after_completion(self):
		from volunteering.volunteering.collaboration_reminders import events_for
		task = self.task(from_date=nowdate(), until_date=add_days(nowdate(), 1), item_data={"reminder_time": "14:20"})
		doc = frappe.get_doc(c.PREFIX + "Item", task["name"])
		events = events_for(doc, self.owner, now_datetime(), "Asia/Kolkata")
		self.assertEqual(len(events), 2)
		self.assertTrue(events[0]["scheduled_at"].endswith("14:20:00+05:30"))
		self.assertEqual(events_for(doc, self.outsider, now_datetime(), "Asia/Kolkata"), [])
		c.update_task(task["name"], "complete", task["modified"])
		self.assertEqual(events_for(frappe.get_doc(doc.doctype, doc.name), self.owner, now_datetime(), "Asia/Kolkata"), [])

	def test_date_only_work_reminds_at_nine_and_deduplicates_deadline(self):
		from volunteering.volunteering.collaboration_reminders import events_for, get_reminders
		task = self.task(from_date=nowdate(), deadline=nowdate())
		events = events_for(frappe.get_doc(c.PREFIX + "Item", task["name"]), self.owner, now_datetime(), "Asia/Kolkata")
		self.assertEqual(len(events), 1)
		self.assertIn("T09:00:00+05:30", events[0]["scheduled_at"])
		self.assertIn(events[0]["key"], [r["key"] for r in get_reminders()["reminders"]])
		with self.assertRaises(frappe.ValidationError):
			self.task(item_data={"reminder_time": "25:30"})


	def test_stage_reminders_follow_current_person_not_all_stage_members(self):
		from volunteering.volunteering.collaboration_reminders import events_for
		tracker = self.tracker(scale="Stages", assignment_mode="Stages", attention_date=nowdate(), stages=[
			{"key":"plan", "label":"Plan", "position":40, "assignee":self.owner},
			{"key":"serve", "label":"Serve", "position":100, "assignee":self.member}])
		doc = frappe.get_doc(c.PREFIX + "Item", tracker["name"])
		self.assertFalse(events_for(doc,self.member,now_datetime(),"Asia/Kolkata"))
		tracker = c.record_progress(tracker["name"],tracker["modified"],"Ready for service",stage="serve")
		self.assertTrue(events_for(frappe.get_doc(doc.doctype,doc.name),self.member,now_datetime(),"Asia/Kolkata"))

	def test_shared_view_reminder_and_shared_private_receipt_are_not_exposed(self):
		from volunteering.volunteering.collaboration_reminders import get_reminders
		task = self.task(from_date=nowdate())
		task = c.share_item(task["name"],[{"user":self.outsider,"access":"View"}],task["modified"])
		frappe.set_user(self.outsider)
		self.assertEqual(get_reminders()["reminders"],[])
		self.assertNotIn(self.room, [r["name"] for r in c.get_collaboration_home()["spaces"]])
		self.assertEqual(frappe.get_list(c.PREFIX+"Entry",filters={"space":self.room},pluck="name"),[])

	def test_shared_access_is_removed_when_chat_role_is_revoked(self):
		task = self.task()
		c.share_item(task["name"],[{"user":self.outsider}],task["modified"])
		frappe.set_user("Administrator")
		user = frappe.get_doc("User",self.outsider)
		user.set("roles",[row for row in user.roles if row.role not in c.CHAT_ROLES]); user.flags.no_welcome_mail=True; user.save(ignore_permissions=True)
		frappe.set_user(self.outsider)
		with self.assertRaises(frappe.PermissionError): c.get_work_item(task["name"])
		self.assertEqual(c._shared_ids(),[])


	def test_invalid_window_and_snooze_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			self.task(from_date=nowdate(), until_date=add_days(nowdate(), -1))
		task = self.task(from_date=nowdate(), until_date=add_days(nowdate(), 2))
		with self.assertRaises(frappe.ValidationError):
			c.update_task(task["name"], "snooze", task["modified"], add_days(nowdate(), 3))

	def test_recurring_monthly_anchor_and_no_duplicates(self):
		task = self.task(from_date="2027-01-31", repeat_pattern="Monthly")
		completed = c.update_task(task["name"], "complete", task["modified"])
		series = frappe.db.get_value(c.PREFIX + "Item", task["name"], "series_key")
		next_task = frappe.get_doc(c.PREFIX + "Item", {"series_key": series, "from_date": "2027-02-28"})
		c.update_task(next_task.name, "fail", str(next_task.modified))
		self.assertTrue(frappe.db.exists(c.PREFIX + "Item", {"series_key": series, "from_date": "2027-03-31"}))
		opened = c.update_task(task["name"], "reopen", completed["modified"])
		c.update_task(task["name"], "complete", opened["modified"])
		self.assertEqual(frappe.db.count(c.PREFIX + "Item", {"series_key": series}), 3)

	def test_task_outcome_cannot_bypass_recurrence_endpoint(self):
		task = self.task()
		with self.assertRaises(frappe.ValidationError):
			c.save_item(self.room, {"status": "Completed"}, task["name"], task["modified"])

	def test_event_dates_and_participants(self):
		with self.assertRaises(frappe.ValidationError):
			c.save_item(self.room, {"item_kind": "Event", "title": "Meeting", "start_at": "2027-01-01 12:00", "end_at": "2027-01-01 11:00"})
		event = c.save_item(self.room, {"item_kind": "Event", "title": "Meeting", "start_at": "2027-01-01 12:00", "end_at": "2027-01-01 13:00", "participants": [self.member]})
		self.assertNotIn(event["name"], [i["name"] for i in c.get_my_work()["calendar"]])
		frappe.set_user(self.member)
		self.assertIn(event["name"], [i["name"] for i in c.get_my_work()["calendar"]])

	def test_shared_nested_list_and_cycle_validation(self):
		rows = [{"id": "a", "content": "Procurement"}, {"id": "b", "parent_id": "a", "content": "Spoons"}]
		item = c.save_item(self.room, {"title": "Kitchen checklist", "item_kind": "List", "item_data": {"rows": rows}})
		frappe.set_user(self.member)
		rows[1]["completed"] = True
		item = c.save_item(self.room, {"item_data": {"rows": rows}}, item["name"], item["modified"])
		self.assertTrue(item["item_data"]["rows"][1]["completed"])
		rows[0]["parent_id"] = "b"
		with self.assertRaises(frappe.ValidationError):
			c.save_item(self.room, {"item_data": {"rows": rows}}, item["name"], item["modified"])

	def test_tracker_scales_validate_finite_and_distinct_stages(self):
		for config in [{"value": 101}, {"scale": "Number", "minimum": 2, "maximum": 1}, {"value": float("nan")},
			{"scale": "Stages", "stages": [{"key": "a", "label": "One", "position": 50}, {"key": "b", "label": "Two", "position": 40}]}]:
			with self.subTest(config=config), self.assertRaises(frappe.ValidationError):
				self.tracker(**config)

	def test_tracker_backdate_keeps_latest_and_history(self):
		item = self.tracker()
		now = now_datetime() - timedelta(minutes=1)
		item = c.record_progress(item["name"], item["modified"], "Latest progress", value=80, effective_at=str(now))
		item = c.record_progress(item["name"], item["modified"], "Older progress", value=20, effective_at=str(now - timedelta(days=2)))
		self.assertEqual(item["item_data"]["value"], 80)
		history = c.get_item_history(item["name"])["history"]
		self.assertEqual(len([e for e in history if e["entry_kind"] == "Progress"]), 2)

	def test_tracker_progress_does_not_complete_tasks(self):
		task = self.task()
		item = self.tracker()
		c.record_progress(item["name"], item["modified"], "Finished tracker", value=100, outcome="Completed")
		self.assertEqual(frappe.db.get_value(c.PREFIX + "Item", task["name"], "status"), "Open")

	def test_number_stage_and_status_updates(self):
		for scale in ["Number", "Stages", "Status"]:
			config = {"scale": scale, "minimum": 0, "maximum": 200, "unit": "meals"}
			if scale != "Number":
				config["stages"] = [{"key": "start", "label": "Planning", "position": 10}, {"key": "end", "label": "Served", "position": 100}]
			item = self.tracker(**config)
			result = c.record_progress(item["name"], item["modified"], "Progress", **({"value": 150} if scale == "Number" else {"stage": "end"}))
			self.assertEqual(result["status"], "Open")

	def test_private_attachment_and_role_revocation(self):
		message = c.post_entry(self.room, "Route document", request_key="file")["name"]
		file = c.upload_attachment(message, "route.txt", base64.b64encode(b"Kitchen distribution route").decode())
		doc = frappe.get_doc("File", {"file_url": file["file_url"]})
		self.assertEqual(doc.is_private, 1)
		self.assertTrue(c.can_read_file(doc, self.member))
		self.assertFalse(c.can_read_file(doc, self.outsider))
		frappe.db.delete("Has Role", {"parent": self.member, "role": ["in", c.CHAT_ROLES]})
		self.assertFalse(c.can_read_file(doc, self.member))
		frappe.set_user(self.member)
		with self.assertRaises(frappe.PermissionError):
			c.get_space(self.room)

	def test_public_attachment_bypass_rejected(self):
		message = c.post_entry(self.room, "File", request_key="private")["name"]
		with self.assertRaises(frappe.PermissionError):
			frappe.get_doc({"doctype": "File", "file_name": "bypass.txt", "content": "Unsafe", "is_private": 0,
				"attached_to_doctype": c.PREFIX + "Entry", "attached_to_name": message}).insert(ignore_permissions=True)

	def test_send_message_with_attachment_retry(self):
		payload = {"space": self.room, "body": "Delivery note", "request_key": "combined",
			"attachments": [{"filename": "note.txt", "content": base64.b64encode(b"Delivery note").decode()}]}
		first = c.send_message(payload)
		self.assertEqual(first, c.send_message(payload))
		self.assertEqual(frappe.db.count("File", {"attached_to_doctype": c.PREFIX + "Entry", "attached_to_name": first["name"]}), 1)

	def test_new_workspaces_do_not_grant_financial_roles(self):
		self.assertNotIn("Accounts Manager", frappe.get_roles(self.owner))
		self.assertNotIn("Projects Manager", frappe.get_roles(self.owner))
		self.assertNotIn("Expense Approver", frappe.get_roles(self.owner))

	def test_home_reminders_respect_membership_and_role(self):
		self.task(from_date=nowdate(), assignee=self.member)
		c.post_entry(self.room, "Delivery is due", request_key="reminder")
		frappe.set_user(self.member)
		self.assertGreaterEqual(c.get_home_summary()["unread"], 1)
		self.assertEqual(c.get_home_summary()["due"], 1)
		frappe.set_user(self.outsider)
		self.assertEqual(c.get_home_summary(), {"unread": 0, "due": 0})

	def test_unscheduled_deadline_task_is_due_and_tracker_attention_is_in_calendar(self):
		task = self.task(deadline=nowdate())
		tracker = self.tracker(attention_date=nowdate())
		work = c.get_my_work()
		self.assertIn(task["name"], [i["name"] for i in work["today"]])
		self.assertIn(tracker["name"], [i["name"] for i in work["calendar"]])

	def test_manager_can_change_title_without_changing_archive_state(self):
		frappe.set_user(self.manager)
		c.save_space({"title": "Updated by manager", "archived": 0}, self.room, c.get_space(self.room)["space"]["modified"])
		self.assertEqual(c.get_space(self.room)["space"]["title"], "Updated by manager")

	def test_pagination_keeps_messages_with_identical_timestamps(self):
		stamp = now_datetime()
		for index in range(53):
			message = c.post_entry(self.room, f"Message {index}", request_key=f"page-{index}")["name"]
			frappe.db.set_value(c.PREFIX + "Entry", message, "creation", stamp, update_modified=False)
		page = c.get_space(self.room)
		older = c.get_space(self.room, before=page["older_cursor"])
		self.assertEqual(len({entry["name"] for entry in page["entries"] + older["entries"]}), 53)
