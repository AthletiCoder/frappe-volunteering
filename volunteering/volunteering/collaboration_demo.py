"""Explicit local-only demo setup. Never invoked by install/migrate or from a website."""
import base64
import frappe
from frappe.utils import add_days, nowdate
from volunteering.volunteering import collaboration as c
from volunteering.volunteering.collaboration_setup import ensure_chat_role


def setup():
	if frappe.local.site not in {"sevamrita.local", "sevamrita-regression-20261027.local"}:
		frappe.throw("Collaboration demo setup is limited to the two local development sites.")
	previous = frappe.session.user
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	ensure_chat_role()
	people = [("ravi", "Ravi", "Menon", "Owner"), ("arjun", "Arjun", "Sharma", "Member"), ("dev", "Dev", "Patil", "Viewer")]
	users = []
	for key, first, last, access in people:
		email = f"demo.chat.{key}@sevamrita.local"
		if not frappe.db.exists("User", email):
			frappe.get_doc({"doctype": "User", "email": email, "first_name": first, "last_name": last,
				"send_welcome_email": 0, "new_password": "DemoChat!2026", "roles": [{"role": role} for role in c.CHAT_ROLES]}).insert(ignore_permissions=True)
		else:
			user = frappe.get_doc("User", email)
			for role in c.CHAT_ROLES:
				if role not in {row.role for row in user.roles}:
					user.append("roles", {"role": role})
			user.save(ignore_permissions=True)
		users.append({"user": email, "access_level": access})
	frappe.set_user(users[0]["user"])
	existing = frappe.get_all(c.PREFIX + "Space", filters={"title": "Pune Community Kitchen", "owner": users[0]["user"]}, pluck="name", limit=1)
	if existing:
		workspace = existing[0]
	else:
		workspace = c.save_space({"title": "Pune Community Kitchen", "space_kind": "Workspace", "members": users})["name"]
		area = c.save_space({"title": "Weekend meal service", "parent_space": workspace})["name"]
		message = c.post_entry(workspace, "Let us plan 200 meals for the weekend. Arjun, please confirm utensils and the delivery route.", request_key="demo-welcome")["name"]
		c.save_item(workspace, {"title": "Confirm utensils with the vendor", "item_kind": "Task", "source_entry": message,
			"assignee": users[1]["user"], "from_date": nowdate(), "until_date": add_days(nowdate(), 2), "priority": "High"})
		c.save_item(workspace, {"title": "Kitchen preparation checklist", "item_kind": "List", "item_data": {"rows": [
			{"id": "supplies", "content": "Arrange kitchen supplies"}, {"id": "spoons", "parent_id": "supplies", "content": "200 reusable spoons", "completed": True},
			{"id": "vessels", "parent_id": "supplies", "content": "Three cooking vessels"}, {"id": "route", "content": "Confirm the distribution route"}]}})
		tracker = c.save_item(workspace, {"title": "Weekend service preparation", "item_kind": "Tracker", "assignee": users[1]["user"],
			"item_data": {"scale": "Stages", "stages": [{"key": "plan", "label": "Plan agreed", "position": 10},
				{"key": "supplies", "label": "Supplies arranged", "position": 45}, {"key": "cooked", "label": "Meals prepared", "position": 85},
				{"key": "served", "label": "Meals distributed", "position": 100}], "next_action": "Confirm utensils", "attention_date": nowdate()}})
		c.record_progress(tracker["name"], tracker["modified"], "The menu and serving plan are agreed.", stage="plan")
		c.save_item(workspace, {"title": "Weekend planning call", "item_kind": "Event", "start_at": f"{add_days(nowdate(), 1)} 10:00:00",
			"end_at": f"{add_days(nowdate(), 1)} 10:30:00", "location": "Pune office", "participants": [row["user"] for row in users[:2]]})
		c.post_entry(area, "Use this area for preparation notes and distribution-day updates.", request_key="area-welcome")
		direct = c.start_direct(users[1]["user"])["name"]
		c.post_entry(direct, "Arjun, please add the vendor confirmation to the kitchen workspace.", request_key="direct-welcome")
	# Ensure each tracker mode has a realistic sample without resetting existing progress.
	for title, config, progress, note in [
		("Volunteer orientation", {"scale": "Percentage", "next_action": "Call the remaining volunteers"}, {"value": 40}, "Four of ten volunteers have completed orientation."),
		("Meals packed for delivery", {"scale": "Number", "minimum": 0, "maximum": 200, "unit": "meals", "next_action": "Continue packing the remaining meals"}, {"value": 75}, "The first 75 meal packets are ready."),
		("Vendor confirmation", {"scale": "Status", "stages": [{"key": "requested", "label": "Requested"}, {"key": "awaiting", "label": "Awaiting response"}, {"key": "confirmed", "label": "Confirmed"}], "next_action": "Call the utensils vendor"}, {"stage": "awaiting"}, "The quotation is sent; the vendor's confirmation is pending."),
	]:
		if not frappe.db.exists(c.PREFIX + "Item", {"space": workspace, "item_kind": "Tracker", "title": title}):
			tracker = c.save_item(workspace, {"title": title, "item_kind": "Tracker", "assignee": users[1]["user"],
				"item_data": {**config, "attention_date": nowdate()}})
			c.record_progress(tracker["name"], tracker["modified"], note, **progress)
	# Add a small readable attachment and a second participant's message on reruns too.
	if not frappe.db.exists(c.PREFIX + "Item", {"space": workspace, "title": "Community kitchen service handover"}):
		c.save_item(workspace, {"item_kind": "Tracker", "title": "Community kitchen service handover", "assignee": users[0]["user"],
			"item_data": {"scale": "Stages", "assignment_mode": "Stages", "attention_date": nowdate(), "attention_until": add_days(nowdate(), 2),
				"stages": [{"key": "planning", "label": "Planning", "position": 30, "assignee": users[0]["user"]},
					{"key": "preparation", "label": "Preparation", "position": 70, "assignee": users[1]["user"]},
					{"key": "distribution", "label": "Distribution", "position": 100, "assignee": users[0]["user"]}]}})
	private = frappe.db.get_value(c.PREFIX + "Space", {"title": "Kitchen coordination notes", "owner": users[0]["user"]}, "name")
	if not private:
		private = c.save_space({"title": "Kitchen coordination notes", "space_kind": "Workspace"})["name"]
	if not frappe.db.exists(c.PREFIX + "Item", {"space": private, "title": "Check meal-delivery contact numbers"}):
		task = c.save_item(private, {"item_kind": "Task", "title": "Check meal-delivery contact numbers", "from_date": nowdate(),
			"description": "Confirm the delivery contacts. This task is shared individually; the coordination chat stays private."})
		c.share_item(task["name"], [{"user": users[1]["user"], "access": "Update"}], task["modified"])

	stream = b"BT /F1 20 Tf 50 780 Td (DEMO - COMMUNITY KITCHEN PLAN) Tj 0 -42 Td /F1 12 Tf (Prepare 200 meals for the weekend service.) Tj 0 -25 Td (Arjun: confirm utensils and the delivery route.) Tj 0 -25 Td (Ravi: coordinate supplies and the planning call.) Tj ET"
	objects = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>", b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
	pdf, offsets = b"%PDF-1.4\n", [0]
	for index, obj in enumerate(objects, 1):
		offsets.append(len(pdf)); pdf += str(index).encode() + b" 0 obj\n" + obj + b"\nendobj\n"
	xref = len(pdf)
	pdf += b"xref\n0 6\n0000000000 65535 f \n" + b"".join(f"{value:010d} 00000 n \n".encode() for value in offsets[1:])
	pdf += f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
	c.send_message({"space": workspace, "body": "Here is the sample kitchen plan for our discussion.", "request_key": "demo-plan-pdf",
		"attachments": [{"filename": "demo-kitchen-plan.pdf", "content": base64.b64encode(pdf).decode()}]})
	frappe.set_user(users[1]["user"])
	c.post_entry(workspace, "I will confirm the utensils today and update the preparation tracker.", request_key="demo-member-reply")
	frappe.db.commit()
	frappe.set_user(previous)
	return {"workspace": workspace, "users": users, "new_user_password": "DemoChat!2026"}


def add_group_examples():
	"""Add intentional review examples without resetting any existing chat or tracker."""
	if frappe.local.site not in {"sevamrita.local", "sevamrita-regression-20261027.local"}:
		frappe.throw("Group examples are restricted to the two local sites.")
	people = {name: f"demo.chat.{name}@sevamrita.local" for name in ("ravi", "arjun", "dev")}
	if not all(c.has_chat_access(user) for user in people.values()):
		frappe.throw("Prepare the existing chat demo accounts first.")
	previous = frappe.session.user
	frappe.set_user(people["ravi"])
	groups = [
		("Talegaon School Support", "Coordinate school kits, student registration and consent forms.", [
			("School kit distribution", {"scale": "Stages", "assignment_mode": "Stages", "stages": [
				{"key": "planning", "label": "Planning", "position": 25, "assignee": people["ravi"]},
				{"key": "procurement", "label": "Procurement", "position": 65, "assignee": people["arjun"]},
				{"key": "distribution", "label": "Distribution", "position": 100, "assignee": people["ravi"]}]},
				{"stage": "procurement"}, "The kit list is agreed and procurement is underway."),
			("Students registered", {"scale": "Number", "minimum": 0, "maximum": 150, "unit": "students"},
				{"value": 86}, "Registered 86 students; verify the remaining class lists."),
			("Parent consent forms", {"scale": "Percentage"}, {"value": 60}, "Consent forms received for sixty percent of the students."),
		]),
		("Powai Health Camp", "Prepare the venue, supplies and participant arrangements for the health camp.", [
			("Health camp readiness", {"scale": "Percentage"}, {"value": 55}, "Volunteer and equipment arrangements are progressing."),
			("Medicine packets prepared", {"scale": "Number", "minimum": 0, "maximum": 250, "unit": "packets"},
				{"value": 110}, "The first 110 medicine packets are ready."),
			("Venue confirmation", {"scale": "Status", "stages": [{"key": "requested", "label": "Requested"},
				{"key": "awaiting", "label": "Awaiting confirmation"}, {"key": "confirmed", "label": "Confirmed"}]},
				{"stage": "confirmed", "outcome": "Completed"}, "The school hall booking is confirmed."),
		]),
		("Hyderabad Volunteer Drive", "Track volunteer onboarding, confirmations and orientation materials.", [
			("Volunteer onboarding", {"scale": "Stages", "assignment_mode": "Stages", "stages": [
				{"key": "shortlist", "label": "Shortlisting", "position": 25, "assignee": people["arjun"]},
				{"key": "orientation", "label": "Orientation", "position": 60, "assignee": people["ravi"]},
				{"key": "ready", "label": "Ready for service", "position": 100, "assignee": people["arjun"]}]},
				{"stage": "orientation"}, "Shortlisting is complete; orientation is underway."),
			("Volunteers confirmed", {"scale": "Number", "minimum": 0, "maximum": 40, "unit": "volunteers"},
				{"value": 22}, "Twenty-two volunteers have confirmed their availability."),
			("Orientation materials", {"scale": "Percentage"}, {"value": 35}, "The introduction and first activity materials are ready."),
		]),
	]
	result = {"created_groups": 0, "created_trackers": 0, "groups": []}
	try:
		for title, welcome, trackers in groups:
			room = frappe.db.get_value(c.PREFIX + "Space", {"title": title, "owner": people["ravi"], "space_kind": "Group"}, "name")
			if not room:
				room = c.save_space({"title": title, "space_kind": "Group", "members": [
					{"user": people["ravi"], "access_level": "Owner"}, {"user": people["arjun"], "access_level": "Member"},
					{"user": people["dev"], "access_level": "Viewer"}]})["name"]
				result["created_groups"] += 1
				c.post_entry(room, welcome, request_key="group-examples-welcome")
			for tracker_title, config, progress, note in trackers:
				if frappe.db.exists(c.PREFIX + "Item", {"space": room, "item_kind": "Tracker", "title": tracker_title}):
					continue
				tracker = c.save_item(room, {"title": tracker_title, "item_kind": "Tracker", "assignee": people["arjun"],
					"item_data": {**config, "attention_date": add_days(nowdate(), 1), "attention_until": add_days(nowdate(), 4)}})
				c.record_progress(tracker["name"], tracker["modified"], note, **progress)
				result["created_trackers"] += 1
			result["groups"].append({"name": room, "title": title})
		frappe.db.commit()
	finally:
		frappe.set_user(previous)
	return result


def archive_test_chats(dry_run=True):
	"""Hide precisely identified browser fixtures from the review site; preserve user work."""
	import json
	import re
	from datetime import datetime
	from pathlib import Path
	if frappe.local.site != "sevamrita.local":
		frappe.throw("This cleanup is restricted to the local review site.")
	owner = "demo.chat.ravi@sevamrita.local"
	allowed = {f"demo.chat.{name}@sevamrita.local" for name in ("ravi", "arjun", "dev")}
	candidates = []
	for row in frappe.get_all(c.PREFIX + "Space", filters={"owner": owner, "title": ["like", "QA kitchen %"], "archived": 0}, fields=["name", "title"]):
		doc = frappe.get_doc(c.PREFIX + "Space", row.name)
		if re.fullmatch(r"QA kitchen \d{13}", doc.title) and not doc.parent_space and {m.user for m in doc.members} <= allowed:
			candidates.append(doc)
	result = {"count": len(candidates), "chats": [{"name": doc.name, "title": doc.title} for doc in candidates]}
	if dry_run or not candidates:
		return result
	ids = [doc.name for doc in candidates]
	rooms = frappe.get_all(c.PREFIX + "Space", filters={"root_space": ["in", ids]}, pluck="name")
	audit = {"site": frappe.local.site, "spaces": [frappe.get_doc(c.PREFIX + "Space", name).as_dict() for name in rooms],
		"items": frappe.get_all(c.PREFIX + "Item", filters={"space": ["in", rooms]}, fields=["*"], limit_page_length=0),
		"entries": frappe.get_all(c.PREFIX + "Entry", filters={"space": ["in", rooms]}, fields=["*"], limit_page_length=0)}
	path = Path(frappe.get_app_path("volunteering")).parent / "output" / f"archived-qa-chats-{datetime.now():%Y%m%d-%H%M%S}.json"
	path.parent.mkdir(exist_ok=True)
	path.write_text(json.dumps(audit, default=str, indent=2))
	for doc in candidates:
		doc.archived = 1
		c._save(doc)
	frappe.db.commit()
	return {**result, "audit_file": str(path), "archived": True}


def setup_interface_examples():
	"""Browser role-matrix fixtures belong only to the disposable regression site."""
	if frappe.local.site != "sevamrita-regression-20261027.local":
		frappe.throw("Interface regression fixtures require the isolated site.")
	previous = frappe.session.user
	frappe.set_user("Administrator")
	frappe.flags.mute_emails = True
	ensure_chat_role()
	try:
		for key, roles in [("web", [c.WEB_ROLE]), ("app", [c.APP_ROLE]), ("both", list(c.CHAT_ROLES))]:
			email = f"demo.interface.{key}@sevamrita.local"
			if frappe.db.exists("User", email):
				user = frappe.get_doc("User", email)
			else:
				user = frappe.new_doc("User")
				user.update({"email": email, "first_name": "Interface", "last_name": key.title(), "send_welcome_email": 0,
					"new_password": "DemoChat!2026"})
			user.set("roles", [{"role": role} for role in ["Employee", *roles]])
			user.flags.no_welcome_mail = True
			user.save(ignore_permissions=True)
		frappe.db.commit()
	finally:
		frappe.set_user(previous)
