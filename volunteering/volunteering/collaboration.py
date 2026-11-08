"""Private, role-gated collaboration shared by Home and the native app."""
from __future__ import annotations

import base64
import hashlib
import json
from contextvars import ContextVar

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate, get_datetime, now_datetime, nowdate

from volunteering.volunteering.collaboration_access import (
	WEB_ROLE, APP_ROLE, CHAT_ROLES, has_chat_access, require_chat_access,
)

ROLE = WEB_ROLE
PREFIX = "Collaboration "
LEVELS = {"Owner", "Manager", "Member", "Viewer"}
KINDS = {"Task", "Event", "List", "Tracker"}
OPEN = {"Open", "In progress"}
PRIORITIES = {"Very low", "Low", "Medium", "High", "Very high"}
_writing_file = ContextVar("collaboration_file_write", default=False)


def _require():
	return require_chat_access()


def _deny():
	frappe.throw(_("This conversation is not available to you."), frappe.PermissionError)


def _text(value, maximum=160, required=False):
	if not isinstance(value, (str, type(None))):
		frappe.throw(_("Enter text, not a structured value."))
	value = (value or "").strip()
	if len(value) > maximum or (required and not value):
		frappe.throw(_("Fill the required text within {0} characters.").format(maximum))
	return value


def _data(value, allowed):
	value = frappe.parse_json(value) if isinstance(value, str) else value
	if not isinstance(value, dict) or set(value) - set(allowed):
		frappe.throw(_("The submitted fields are invalid."))
	return dict(value)


def _json(value, default):
	return frappe.parse_json(value) if value else default


def _insert(kind, data):
	doc = frappe.get_doc({"doctype": PREFIX + kind, **data})
	_encode_json_fields(doc)
	doc.flags.collaboration_write = True
	return doc.insert(ignore_permissions=True)


def _save(doc):
	_encode_json_fields(doc)
	doc.flags.collaboration_write = True
	doc.save(ignore_permissions=True)
	return doc


def _encode_json_fields(doc):
	for field in doc.meta.get("fields"):
		if field.fieldtype == "JSON" and isinstance(doc.get(field.fieldname), (list, dict)):
			doc.set(field.fieldname, json.dumps(doc.get(field.fieldname)))


def _version(doc, expected):
	if not expected or str(doc.modified) != str(expected):
		frappe.throw(_("This record changed. Refresh it before saving your changes."))


def _root_ids(user=None):
	if not has_chat_access(user):
		return []
	return frappe.get_all(PREFIX + "Member", filters={"user": user or frappe.session.user,
		"parenttype": PREFIX + "Space"}, pluck="parent", limit_page_length=0)


def _space(name, write=False, lock=False):
	_require()
	if not frappe.db.exists(PREFIX + "Space", name):
		_deny()
	room = frappe.get_doc(PREFIX + "Space", name)
	root_id = room.root_space or room.name
	root = frappe.get_doc(PREFIX + "Space", root_id, for_update=write or lock)
	member = next((row for row in root.members if row.user == frappe.session.user), None)
	if not member:
		_deny()
	if write and (member.access_level == "Viewer" or root.archived or room.archived):
		frappe.throw(_("This workspace is read-only for you."), frappe.PermissionError)
	if write and room.name != root.name:
		room = frappe.get_doc(PREFIX + "Space", room.name, for_update=True)
	return room, root, member.access_level


def _name(user):
	return frappe.db.get_value("User", user, "full_name") or user


def _members(root):
	return [{"user": row.user, "full_name": _name(row.user), "access_level": row.access_level,
		"chat_enabled": has_chat_access(row.user)} for row in root.members]


def _allowed_person(user, root=None):
	if not has_chat_access(user) or (root and user not in {row.user for row in root.members}):
		frappe.throw(_("Select an enabled chat user who belongs to this workspace."))
	return user


def _allowed_assignee(user, root):
	_allowed_person(user, root)
	if next(row for row in root.members if row.user == user).access_level == "Viewer":
		frappe.throw(_("Assign work to a contributing member, not a viewer."))
	return user


def _linked_entry(name, space):
	if name and not frappe.db.exists(PREFIX + "Entry", {"name": name, "space": space, "is_deleted": 0}):
		frappe.throw(_("The linked message must belong to this conversation."))
	return name or None


def _room_payload(room, root, level):
	title = room.title
	if room.space_kind == "Direct":
		title = ", ".join(_name(row.user) for row in root.members if row.user != frappe.session.user)
	return {"name": room.name, "title": title, "space_kind": room.space_kind,
		"root_space": root.name, "parent_space": room.parent_space, "project": room.project,
		"archived": bool(room.archived or root.archived), "modified": str(room.modified),
		"access_level": level, "can_post": level != "Viewer" and not (room.archived or root.archived),
		"can_manage": level in {"Owner", "Manager"} and room.space_kind != "Direct",
		"members": _members(root)}


def _share_level(doc, user=None):
	return next((row.get("access") for row in _json(doc.get("shares"), []) if row.get("user") == (user or frappe.session.user)), None)


def _shared_ids(user=None):
	user = user or frappe.session.user
	if not has_chat_access(user):
		return []
	return [row.name for row in frappe.get_all(PREFIX + "Item", filters={"item_kind": ["in", ["Task", "Tracker"]],
		"shares": ["like", "%" + user.replace("%", "\\%").replace("_", "\\_") + "%"]}, fields=["name", "shares"], limit_page_length=0)
		if any(share.get("user") == user for share in _json(row.shares, []))]


def _can_share_item(doc, level):
	return doc.item_kind in {"Task", "Tracker"} and (level in {"Owner", "Manager"} or level == "Member" and doc.owner == frappe.session.user)


def _item_payload(doc, level=None):
	config = _json(doc.item_data, {})
	if doc.item_kind == "Tracker":
		for stage in config.get("stages", []):
			stage["assignee_name"] = _name(stage["assignee"]) if stage.get("assignee") else ""
	can_update = level not in {None, "Viewer", "SharedView"} and (doc.item_kind == "Tracker" or _can_edit_item(doc, level))
	return {**{key: doc.get(key) for key in ("name", "space", "item_kind", "title", "description", "source_entry",
		"assignee", "status", "priority", "from_date", "until_date", "deadline", "snoozed_until",
		"repeat_pattern", "repeat_until", "start_at", "end_at", "location", "current_effective_at")},
		"owner": doc.owner, "modified": str(doc.modified), "assignee_name": _name(doc.assignee) if doc.assignee else "",
		"participants": _json(doc.participants, []), "item_data": config,
		"can_update": bool(can_update), "can_add_files": bool(doc.item_kind == "Tracker" and level in {"Owner", "Manager", "Member"}), "can_share": _can_share_item(doc, level),
		"can_configure": bool(level in {"Owner", "Manager"} or level == "Member" and doc.owner == frappe.session.user),
		"shares": [{**row, "full_name": _name(row["user"])} for row in _json(doc.get("shares"), [])] if _can_share_item(doc, level) else [],
		"shared_with_me": bool(_share_level(doc)),
		"can_edit": bool(level not in {None, "SharedView", "SharedUpdate"} and _can_edit_item(doc, level))}


def _can_edit_item(doc, level):
	return level in {"Owner", "Manager", "SharedUpdate"} or (level == "Member" and
		(doc.item_kind == "List" or frappe.session.user in {doc.owner, doc.assignee}))


def _read_item(name, write=False):
	_require()
	doc = frappe.get_doc(PREFIX + "Item", name, for_update=write)
	room = frappe.get_doc(PREFIX + "Space", doc.space)
	root = frappe.get_doc(PREFIX + "Space", room.root_space or room.name)
	member = next((row for row in root.members if row.user == frappe.session.user), None)
	shared = _share_level(doc) if doc.item_kind in {"Task", "Tracker"} else None
	if not member and not shared:
		_deny()
	level = member.access_level if member else "SharedView"
	if shared == "Update" and level in {"Viewer", "SharedView"}:
		level = "SharedUpdate"
	if room.archived or root.archived:
		level = "Viewer"
	if write and level in {"Viewer", "SharedView"}:
		_deny()
	return doc, room, root, level


@frappe.whitelist(methods=["POST"])
def get_work_item(name):
	doc, room, root, level = _read_item(name)
	if doc.item_kind not in {"Task", "Tracker"}:
		_deny()
	member = can_read_space(room.name)
	space = _room_payload(room, root, level) if member else {"name": room.name, "title": room.title,
		"can_post": False, "can_manage": False, "members": [], "access_level": level, "item_only": True}
	return {"space": space, "items": [_item_payload(doc, level)], "entries": [], "item_only": not member}


@frappe.whitelist(methods=["POST"])
def share_item(name, shares, expected_modified):
	doc, room, root, level = _read_item(name, write=True)
	if not _can_share_item(doc, level):
		_deny()
	_version(doc, expected_modified)
	shares = _json(shares, []) if isinstance(shares, str) else shares
	if not isinstance(shares, list) or len(shares) > 50:
		frappe.throw(_("Share with up to 50 people."))
	cleaned, seen = [], set()
	for row in shares:
		row = _data(row, {"user", "access", "full_name"})
		user = _allowed_person(row.get("user"))
		if user in seen or row.get("access", "View") not in {"View", "Update"}:
			frappe.throw(_("Choose distinct people and valid sharing permissions."))
		seen.add(user)
		cleaned.append({"user": user, "access": row.get("access", "View")})
	doc.shares = cleaned
	_save(doc)
	_entry(doc.space, f"Updated sharing: {doc.title}", item=doc.name)
	_publish(doc.space, root)
	return _item_payload(doc, level)


def _entry_payload(doc, level):
	editable = not doc.is_deleted and doc.entry_kind not in {"System", "Progress"} and level != "Viewer"
	return {"name": doc.name, "space": doc.space, "body": "Message removed" if doc.is_deleted else doc.body,
		"entry_kind": doc.entry_kind, "owner": doc.owner, "author_name": _name(doc.owner), "creation": str(doc.creation),
		"edited_at": doc.edited_at, "modified": str(doc.modified), "is_deleted": bool(doc.is_deleted), "source_entry": doc.source_entry,
		"item": doc.item, "snapshot": _json(doc.snapshot, {}),
		"can_edit": editable and doc.owner == frappe.session.user,
		"can_remove": editable and (doc.owner == frappe.session.user or level in {"Owner", "Manager"}),
		"attachments": [] if doc.is_deleted else frappe.get_all("File", filters={"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name, "is_private": 1}, fields=["name", "file_name", "file_url", "file_size"])}


@frappe.whitelist(methods=["POST"])
def get_directory(query=""):
	_require()
	query = _text(query, 100)
	users = frappe.get_all("Has Role", filters={"parenttype": "User", "role": ["in", CHAT_ROLES]}, pluck="parent", limit_page_length=0)
	return frappe.get_all("User", filters={"name": ["in", users or ["__none__"]], "enabled": 1},
		or_filters={"full_name": ["like", f"%{query}%"], "name": ["like", f"%{query}%"]},
		fields=["name", "full_name"], order_by="full_name", limit_page_length=100)


@frappe.whitelist(methods=["POST"])
def get_collaboration_home():
	user = _require()
	rooms = frappe.get_all(PREFIX + "Space", filters={"root_space": ["in", _root_ids() or ["__none__"]]},
		fields=["name"], order_by="modified desc", limit_page_length=300)
	output = []
	for value in rooms:
		room, root, level = _space(value.name)
		payload = _room_payload(room, root, level)
		last = frappe.get_all(PREFIX + "Entry", filters={"space": room.name},
			fields=["name", "body", "creation", "entry_kind"], order_by="creation desc, name desc", limit_page_length=1)
		payload["last_entry"] = last[0] if last else None
		state = frappe.db.get_value(PREFIX + "Read State", {"space": room.name, "user": user},
			["read_at", "delivered_through"], as_dict=True) or frappe._dict()
		payload["delivery_pending"] = bool(last and (not state.delivered_through or last[0].creation > state.delivered_through))
		filters = {"space": room.name, "owner": ["!=", user], "is_deleted": 0}
		if state.read_at:
			filters["creation"] = [">", state.read_at]
		payload["unread"] = frappe.db.count(PREFIX + "Entry", filters)
		output.append(payload)
	return {"user": user, "spaces": output, "directory": get_directory(), "today": nowdate(),
		"isolated_test_site": frappe.local.site == "sevamrita-regression-20261027.local",
		"projects": frappe.get_list("Project", fields=["name", "project_name"], limit_page_length=100)
			if frappe.has_permission("Project", "read") else []}


@frappe.whitelist(methods=["POST"])
def save_space(payload, name=None, expected_modified=None):
	user = _require()
	data = _data(payload, {"title", "space_kind", "parent_space", "project", "members", "archived"})
	if name:
		room, root, level = _space(name)
		root = frappe.get_doc(PREFIX + "Space", root.name, for_update=True)
		member = next((row for row in root.members if row.user == user), None)
		if not member:
			_deny()
		level = member.access_level
		room = root if room.name == root.name else frappe.get_doc(PREFIX + "Space", room.name, for_update=True)
		_version(room, expected_modified)
		if level not in {"Owner", "Manager"} or room.space_kind == "Direct":
			_deny()
	else:
		parent = data.get("parent_space")
		if parent:
			parent_doc, root, level = _space(parent, write=True)
			if parent_doc.space_kind == "Direct" or level not in {"Owner", "Manager"}:
				_deny()
		else:
			root, level = None, "Owner"
		room = frappe.new_doc(PREFIX + "Space")
		room.space_kind = "Area" if parent else data.get("space_kind", "Workspace")
		if room.space_kind not in {"Group", "Workspace", "Area"} or (room.space_kind == "Area" and not parent):
			frappe.throw(_("Choose a group or workspace."))
		room.root_space = root.name if root else None
	room.title = _text(data.get("title", room.title), 160, True)
	parent_id = data.get("parent_space", room.parent_space)
	if parent_id:
		parent_doc, parent_root, _level = _space(parent_id)
		if not room.root_space or parent_root.name != room.root_space or parent_id == room.name:
			frappe.throw(_("An area must stay inside its workspace."))
		chain = [parent_id]
		while parent_doc.parent_space:
			chain.append(parent_doc.parent_space)
			if len(chain) > 8 or room.name in chain:
				frappe.throw(_("Too many nested areas or a circular parent."))
			parent_doc = frappe.get_doc(PREFIX + "Space", parent_doc.parent_space)
	elif room.root_space and room.name != room.root_space:
		frappe.throw(_("Select the parent workspace for this area."))
	room.parent_space = parent_id
	if "project" in data:
		project = data["project"]
		if project and not frappe.has_permission("Project", "read", doc=frappe.get_doc("Project", project)):
			_deny()
		room.project = project or None
	if "members" in data and not parent_id:
		members = data["members"]
		if not isinstance(members, list) or not 1 <= len(members) <= 100:
			frappe.throw(_("Choose between 1 and 100 members."))
		seen, cleaned = set(), []
		previous = {row.user: row.access_level for row in room.members}
		for value in members:
			value = _data(value, {"user", "access_level"})
			member_user, access = value.get("user"), value.get("access_level", "Member")
			if access not in LEVELS or member_user in seen:
				frappe.throw(_("Choose distinct members and valid access levels."))
			# Existing disabled members can be retained or removed, never added anew.
			if member_user not in previous:
				_allowed_person(member_user)
			seen.add(member_user)
			cleaned.append({"user": member_user, "access_level": access})
		if not name and user not in seen:
			cleaned.append({"user": user, "access_level": "Owner"})
		if not any(row["access_level"] == "Owner" for row in cleaned):
			frappe.throw(_("Keep at least one workspace owner."))
		if not name and next(row for row in cleaned if row["user"] == user)["access_level"] != "Owner":
			frappe.throw(_("The creator must be an owner."))
		if level == "Manager":
			new = {row["user"]: row["access_level"] for row in cleaned}
			for uid in set(previous) | set(new):
				if previous.get(uid) in {"Owner", "Manager"} or new.get(uid) in {"Owner", "Manager"}:
					if previous.get(uid) != new.get(uid):
						_deny()
		room.set("members", cleaned)
	elif not name and not parent_id:
		room.append("members", {"user": user, "access_level": "Owner"})
	if "archived" in data:
		if level != "Owner" and cint(data["archived"]) != cint(room.archived):
			_deny()
		room.archived = cint(data["archived"])
	_save(room)
	if not room.root_space:
		room.db_set("root_space", room.name, update_modified=False)
	return {"name": room.name, "modified": str(room.modified)}


@frappe.whitelist(methods=["POST"])
def start_direct(user):
	current = _require()
	_allowed_person(user)
	if user == current:
		frappe.throw(_("Choose another person."))
	key = hashlib.sha256(json.dumps(sorted([current, user])).encode()).hexdigest()
	# The user row serialises simultaneous starts from either participant until commit.
	frappe.db.get_value("User", sorted([current, user])[0], "name", for_update=True)
	existing = frappe.db.get_value(PREFIX + "Space", {"direct_key": key}, "name")
	if existing:
		_space(existing)
		return {"name": existing}
	room = _insert("Space", {"title": "Direct conversation", "space_kind": "Direct", "direct_key": key,
		"members": [{"user": uid, "access_level": "Member"} for uid in (current, user)]})
	room.db_set("root_space", room.name, update_modified=False)
	return {"name": room.name}


@frappe.whitelist(methods=["POST"])
def get_space(name, before=None, item=None):
	room, root, level = _space(name)
	content_level = "Viewer" if room.archived or root.archived else level
	condition, params = "", [name]
	if before:
		anchor = frappe.db.get_value(PREFIX + "Entry", {"space": name, "name": before}, "creation")
		if not anchor:
			_deny()
		condition = " and (creation < %s or (creation = %s and name < %s))"
		params.extend([anchor, anchor, before])
	rows = frappe.db.sql("select name from `tabCollaboration Entry` where space=%s" + condition +
		" order by creation desc, name desc limit 51", params, as_dict=True)
	entries = [_entry_payload(frappe.get_doc(PREFIX + "Entry", row.name), content_level) for row in reversed(rows[:50])]
	space_payload = _room_payload(room, root, level)
	receipts = _receipt_cursors(name)
	own = receipts.get(frappe.session.user, frappe._dict())
	recipients = _receipt_recipients(space_payload["members"], receipts)
	receipt_through = {field: min((str(cursor.get(field) or "") for _member, cursor in recipients), default="")
		for field in ("delivered_through", "seen_through")}
	items = frappe.get_all(PREFIX + "Item", filters={"space": name}, fields=["name"], order_by="modified desc", limit_page_length=300)
	if item and item not in {row.name for row in items}:
		# A direct tracker link can refer to an older item outside the initial list.
		if not frappe.db.exists(PREFIX + "Item", {"name": item, "space": name}):
			_deny()
		items.append(frappe._dict(name=item))
	return {"space": space_payload, "entries": entries,
		"delivered_through": str(own.delivered_through or ""), "seen_through": str(own.seen_through or ""),
		"receipt_through": receipt_through,
		"current_progress": _current_progress(name),
		"older_cursor": rows[49].name if len(rows) > 50 else None,
		"items": [_item_payload(frappe.get_doc(PREFIX + "Item", row.name), content_level) for row in items]}


def _current_progress(space):
	# A later-recorded backdated update is history. Break equal effective dates by record order.
	rows = frappe.db.sql("""
		select e.item, e.name
		from `tabCollaboration Entry` e
		join `tabCollaboration Item` i on i.name = e.item and i.space = e.space
		where e.space = %s and e.entry_kind = 'Progress'
			and cast(json_unquote(json_extract(e.snapshot, '$.effective_at')) as datetime(6)) = i.current_effective_at
		order by e.creation desc, e.name desc
	""", (space,))
	current = {}
	for item, entry in rows:
		current.setdefault(item, entry)
	return current


def _receipt_cursors(space):
	rows = frappe.get_all(PREFIX + "Read State", filters={"space": space},
		fields=["user", "delivered_through", "seen_through"], limit_page_length=0)
	return {row.user: row for row in rows}


def _receipt_recipients(members, cursors):
	return [(member, cursors.get(member["user"], frappe._dict())) for member in members
		if member["user"] != frappe.session.user and member["chat_enabled"]]


def _receipt_status(cursor, stamp):
	if cursor.seen_through and cursor.seen_through >= stamp:
		return 3
	if cursor.delivered_through and cursor.delivered_through >= stamp:
		return 2
	return 1


@frappe.whitelist(methods=["POST"])
def get_message_info(name):
	_require()
	doc = frappe.get_doc(PREFIX + "Entry", name)
	_room, root, _level = _space(doc.space)
	if doc.owner != frappe.session.user or doc.is_deleted or doc.entry_kind == "System":
		_deny()
	recipients = _receipt_recipients(_members(root), _receipt_cursors(doc.space))
	return {"recipients": [{"full_name": member["full_name"], "user": member["user"],
		"status": _receipt_status(cursor, doc.creation)} for member, cursor in recipients]}


def _publish(space, root):
	for member in root.members:
		if has_chat_access(member.user):
			frappe.publish_realtime("collaboration_changed", {"space": space}, user=member.user, after_commit=True)


def _entry(space, body, kind="System", item=None, source=None, snapshot=None, request_key=None):
	return _insert("Entry", {"space": space, "body": body, "entry_kind": kind,
		"source_entry": source, "item": item, "snapshot": snapshot, "request_key": request_key})


@frappe.whitelist(methods=["POST"])
def post_entry(space, body="", entry_kind="Message", request_key=None, source_entry=None):
	room, root, _level = _space(space, write=True)
	if entry_kind not in {"Message", "Note", "Decision", "Blocker", "Milestone"}:
		frappe.throw(_("Choose a supported entry type."))
	body = _text(body, 12000, True)
	key = _text(request_key, 100, True)
	key = hashlib.sha256(f"{frappe.session.user}:{space}:{key}".encode()).hexdigest()
	existing = frappe.db.get_value(PREFIX + "Entry", {"request_key": key}, "name")
	if existing:
		prior = frappe.get_doc(PREFIX + "Entry", existing)
		if prior.body != body or prior.entry_kind != entry_kind or (prior.source_entry or None) != (source_entry or None):
			frappe.throw(_("This send key was already used for another message. Refresh before sending."))
		return {"name": existing}
	doc = _insert("Entry", {"space": space, "body": body, "entry_kind": entry_kind,
		"request_key": key, "source_entry": _linked_entry(source_entry, space)})
	_publish(space, root)
	return {"name": doc.name}


@frappe.whitelist(methods=["POST"])
def send_message(payload):
	"""Save the message and all attachments together, with safe retry deduplication."""
	data = _data(payload, {"space", "body", "entry_kind", "request_key", "source_entry", "attachments"})
	_space(data.get("space"), write=True)
	uploads = data.pop("attachments", [])
	if not isinstance(uploads, list) or len(uploads) > 5:
		frappe.throw(_("Choose at most five attachments."))
	key = hashlib.sha256(f"{frappe.session.user}:{data.get('space')}:{data.get('request_key')}".encode()).hexdigest()
	existing = frappe.db.get_value(PREFIX + "Entry", {"request_key": key}, "name")
	result = post_entry(**data)
	if not existing:
		for value in uploads:
			value = _data(value, {"filename", "content"})
			upload_attachment(result["name"], value.get("filename"), value.get("content"))
	return result


@frappe.whitelist(methods=["POST"])
def edit_entry(name, body=None, remove=False, expected_modified=None):
	_require()
	space = frappe.db.get_value(PREFIX + "Entry", name, "space")
	_room, root, level = _space(space, write=True)
	doc = frappe.get_doc(PREFIX + "Entry", name, for_update=True)
	remove = bool(cint(remove))
	if doc.is_deleted or doc.entry_kind in {"System", "Progress"} or (
		doc.owner != frappe.session.user and not (remove and level in {"Owner", "Manager"})
	):
		_deny()
	_version(doc, expected_modified)
	doc.is_deleted = cint(remove)
	doc.body = "" if remove else _text(body, 12000, True)
	doc.edited_at = now_datetime()
	_save(doc)
	_publish(doc.space, root)
	return {"name": name}


@frappe.whitelist(methods=["POST"])
def mark_read(space, entry):
	return _mark_received(space, entry, ("read_at",))


@frappe.whitelist(methods=["POST"])
def mark_delivered(space, entry):
	return _mark_received(space, entry, ("delivered_through",))


@frappe.whitelist(methods=["POST"])
def mark_seen(space, entry):
	return _mark_received(space, entry, ("read_at", "delivered_through", "seen_through"))


def _mark_received(space, entry, fields):
	_space(space, lock=True)
	stamp = frappe.db.get_value(PREFIX + "Entry", {"name": entry, "space": space}, "creation")
	if not stamp:
		_deny()
	key = hashlib.sha256(f"{space}:{frappe.session.user}".encode()).hexdigest()
	existing = frappe.db.get_value(PREFIX + "Read State", {"state_key": key}, "name", for_update=True)
	if existing:
		doc = frappe.get_doc(PREFIX + "Read State", existing, for_update=True)
		updates = {field: stamp for field in fields if not doc.get(field) or get_datetime(doc.get(field)) < stamp}
		if updates:
			doc.update(updates)
			_save(doc)
	else:
		_insert("Read State", {"space": space, "user": frappe.session.user, "state_key": key,
			**dict.fromkeys(fields, stamp)})
	return {"read": "read_at" in fields}


def _dates(data):
	for field in ("from_date", "until_date", "deadline", "snoozed_until", "repeat_until"):
		if data.get(field):
			data[field] = str(getdate(data[field]))
	if data.get("until_date") and (not data.get("from_date") or data["until_date"] < data["from_date"]):
		frappe.throw(_("The action window must end on or after its start date."))
	if data.get("snoozed_until") and (not data.get("from_date") or
		data["snoozed_until"] < data["from_date"] or
		data["snoozed_until"] > (data.get("until_date") or data["from_date"]) or data["snoozed_until"] < nowdate()):
		frappe.throw(_("Snooze must be within the action window and not in the past."))


def _reminder_time(value):
	import re
	value = _text(value, 8)
	if value and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d(?::00)?", value):
		frappe.throw(_("Choose a reminder time between 00:00 and 23:59."))
	return value[:5] or None


def _tracker(data, root=None):
	data = _data(data, {"scale", "minimum", "maximum", "unit", "stages", "value", "stage", "next_action", "attention_date", "attention_until", "assignment_mode", "reminder_time"})
	if data.get("scale") not in {"Percentage", "Number", "Stages", "Status"}:
		frappe.throw(_("Choose a tracker scale."))
	data["assignment_mode"] = data.get("assignment_mode") or "Single"
	if data["assignment_mode"] not in {"Single", "Stages"} or data["assignment_mode"] == "Stages" and data["scale"] not in {"Stages", "Status"}:
		frappe.throw(_("Stage assignment needs a tracker with stages or statuses."))
	data["reminder_time"] = _reminder_time(data.get("reminder_time"))
	data["next_action"] = _text(data.get("next_action"), 500)
	data["unit"] = _text(data.get("unit"), 40)
	for key in ("attention_date", "attention_until"):
		if data.get(key):
			data[key] = str(getdate(data[key]))
	if data.get("attention_until") and (not data.get("attention_date") or data["attention_until"] < data["attention_date"]):
		frappe.throw(_("Choose a valid tracker attention window."))
	if data["scale"] in {"Percentage", "Number"}:
		try:
			low, high = (0, 100) if data["scale"] == "Percentage" else (float(data.get("minimum", 0)), float(data.get("maximum", 100)))
			value = float(data["value"]) if data.get("value") is not None else None
			import math
			if not math.isfinite(low) or not math.isfinite(high) or high <= low or value is not None and (not math.isfinite(value) or not low <= value <= high):
				raise ValueError
		except (ValueError, TypeError):
			frappe.throw(_("Tracker values must be finite numbers inside its scale."))
		data.update(minimum=low, maximum=high, value=value, stage=None, stages=[])
	else:
		stages = data.get("stages") or []
		if not isinstance(stages, list) or not 1 <= len(stages) <= 30:
			frappe.throw(_("Configure between 1 and 30 stages or statuses."))
		seen, cleaned, previous = set(), [], -1
		for stage in stages:
			stage = _data(stage, {"key", "label", "position", "assignee", "assignee_name"})
			key = _text(stage.get("key"), 60, True)
			if key in seen:
				frappe.throw(_("Stage identifiers must be distinct."))
			seen.add(key)
			try:
				position = float(stage.get("position", 0)) if data["scale"] == "Stages" else None
			except (ValueError, TypeError):
				frappe.throw(_("Stage percentages must be numbers within 0–100."))
			if position is not None and not previous < position <= 100:
				frappe.throw(_("Stage percentages must increase, within 0–100."))
			previous = position if position is not None else previous
			assignee = None
			if data["assignment_mode"] == "Stages":
				if not root or not stage.get("assignee"):
					frappe.throw(_("Choose a person for every stage."))
				assignee = _allowed_assignee(stage["assignee"], root)
			cleaned.append({"key": key, "label": _text(stage.get("label"), 100, True), "position": position, "assignee": assignee})
		if data.get("stage") and data["stage"] not in seen:
			frappe.throw(_("Select a configured status."))
		data.update(stages=cleaned, value=None, minimum=None, maximum=None)
	return data


def _list_rows(data, root):
	data = _data(data, {"rows"})
	rows = data.get("rows", [])
	if not isinstance(rows, list) or len(rows) > 300:
		frappe.throw(_("A list can have at most 300 entries."))
	cleaned, parents = [], {}
	for row in rows:
		row = _data(row, {"id", "parent_id", "content", "completed", "priority"})
		key = _text(row.get("id"), 60, True)
		if key in parents:
			frappe.throw(_("List identifiers must be distinct."))
		parents[key] = row.get("parent_id") or None
		priority = row.get("priority", "Medium")
		if priority not in PRIORITIES:
			frappe.throw(_("Choose a valid importance."))
		cleaned.append({"id": key, "parent_id": parents[key], "content": _text(row.get("content"), 2000, True),
			"completed": bool(row.get("completed")), "priority": priority})
	for key, parent in parents.items():
		seen = {key}
		while parent:
			if parent not in parents or parent in seen:
				frappe.throw(_("List nesting must stay inside this list without cycles."))
			seen.add(parent)
			parent = parents[parent]
	return {"rows": cleaned}


ITEM_FIELDS = {"title", "item_kind", "description", "source_entry", "assignee", "status", "priority",
	"from_date", "until_date", "deadline", "snoozed_until", "repeat_pattern", "repeat_until",
	"start_at", "end_at", "location", "participants", "item_data"}


@frappe.whitelist(methods=["POST"])
def save_item(space, payload, name=None, expected_modified=None):
	_room, root, level = _space(space, write=True)
	data = _data(payload, ITEM_FIELDS)
	if name:
		doc = frappe.get_doc(PREFIX + "Item", name, for_update=True)
		if doc.space != space or not _can_edit_item(doc, level):
			_deny()
		_version(doc, expected_modified)
		if data.get("item_kind", doc.item_kind) != doc.item_kind:
			frappe.throw(_("The item type cannot be changed."))
		if doc.item_kind == "Task" and data.get("status", doc.status) != doc.status:
			frappe.throw(_("Use the task's Complete, Failed or Reopen actions to change its outcome."))
	else:
		doc = frappe.new_doc(PREFIX + "Item")
		doc.space = space
		doc.item_kind = data.get("item_kind")
	if doc.item_kind not in KINDS:
		frappe.throw(_("Choose Task, Event, List or Tracker."))
	for key in ITEM_FIELDS - {"item_data", "participants", "item_kind"}:
		if key in data:
			setattr(doc, key, data[key] or None)
	doc.title = _text(doc.title, 160, True)
	doc.description = _text(doc.description, 12000)
	doc.source_entry = _linked_entry(doc.source_entry, space)
	doc.status = doc.status or "Open"
	if not name and doc.status != "Open":
		frappe.throw(_("New work items must start open."))
	doc.priority = doc.priority or "Medium"
	if doc.status not in OPEN | {"Completed", "Failed", "Cancelled"} or doc.priority not in PRIORITIES:
		frappe.throw(_("Choose a valid status and priority."))
	if doc.assignee:
		_allowed_assignee(doc.assignee, root)
	elif doc.item_kind == "Task":
		doc.assignee = frappe.session.user
	dates = {key: doc.get(key) for key in ("from_date", "until_date", "deadline", "snoozed_until", "repeat_until")}
	_dates(dates)
	doc.update(dates)
	doc.repeat_pattern = doc.repeat_pattern or "None"
	if doc.repeat_pattern not in {"None", "Daily", "Weekly", "Monthly"}:
		frappe.throw(_("Choose a supported recurrence."))
	if doc.repeat_pattern != "None":
		if doc.item_kind != "Task" or not doc.from_date or doc.repeat_until and getdate(doc.repeat_until) < getdate(doc.from_date):
			frappe.throw(_("Recurring tasks require a valid start and optional end date."))
		doc.series_key = doc.series_key or frappe.generate_hash(length=20)
		doc.occurrence_key = doc.occurrence_key or hashlib.sha256(f"{doc.series_key}:{doc.from_date}".encode()).hexdigest()
		doc.repeat_anchor_day = doc.repeat_anchor_day or getdate(doc.from_date).day
	if doc.item_kind == "Event":
		if not doc.start_at or not doc.end_at or get_datetime(doc.end_at) <= get_datetime(doc.start_at):
			frappe.throw(_("Events need an end time after their start time."))
		participants = data.get("participants", _json(doc.participants, []))
		if not isinstance(participants, list) or len(participants) > 100:
			frappe.throw(_("Select valid participants."))
		doc.participants = list(dict.fromkeys(_allowed_person(uid, root) for uid in participants))
		doc.location = _text(doc.location, 160)
	if doc.item_kind == "Tracker":
		if name and level not in {"Owner", "Manager"} and doc.owner != frappe.session.user:
			_deny()
		doc.item_data = _tracker(data.get("item_data", _json(doc.item_data, {})), root)
		if doc.item_data["assignment_mode"] == "Stages":
			doc.assignee = None
		elif not doc.assignee:
			doc.assignee = _allowed_assignee(frappe.session.user, root)
	elif doc.item_kind == "Task":
		config = _data(data.get("item_data", _json(doc.item_data, {})) or {}, {"reminder_time", "scale"})
		# Earlier native builds sent this unused tracker default with new tasks.
		if config.get("scale") == "Percentage":
			config.pop("scale")
		config = _data(config, {"reminder_time"})
		doc.item_data = {"reminder_time": _reminder_time(config.get("reminder_time"))}
	elif doc.item_kind == "List":
		doc.item_data = _list_rows(data.get("item_data", _json(doc.item_data, {})), root)
	_save(doc)
	if not name:
		_entry(space, f"Created {doc.item_kind.lower()}: {doc.title}", item=doc.name, source=doc.source_entry)
	_publish(space, root)
	return _item_payload(doc, level)


def _item(name):
	doc, _room, root, level = _read_item(name, write=True)
	return doc, root, level


@frappe.whitelist(methods=["POST"])
def update_task(name, action, expected_modified, date=None):
	doc, root, level = _item(name)
	if doc.item_kind != "Task" or not _can_edit_item(doc, level):
		_deny()
	_version(doc, expected_modified)
	if action in {"start", "complete", "fail", "reopen"}:
		previous = doc.status
		doc.status = {"start": "In progress", "complete": "Completed", "fail": "Failed", "reopen": "Open"}[action]
	elif action == "snooze":
		doc.snoozed_until = str(getdate(date)) if date else None
		_dates({key: doc.get(key) for key in ("from_date", "until_date", "snoozed_until")})
	elif action == "postpone":
		if not date or not doc.from_date or getdate(date) <= getdate(doc.from_date):
			frappe.throw(_("Choose a later start date."))
		delta = (getdate(date) - getdate(doc.from_date)).days
		doc.from_date = getdate(date)
		doc.until_date = add_days(doc.until_date, delta) if doc.until_date else None
		doc.snoozed_until = None
	else:
		frappe.throw(_("Choose a supported task action."))
	_save(doc)
	_entry(doc.space, f"{doc.title}: {action}", item=doc.name, snapshot={"status": doc.status, "from_date": str(doc.from_date or "")})
	if action in {"complete", "fail"} and previous in OPEN and doc.repeat_pattern != "None":
		start = getdate(doc.from_date)
		if doc.repeat_pattern == "Monthly":
			import calendar
			next_month = getdate(add_months(start.replace(day=1), 1))
			next_date = next_month.replace(day=min(doc.repeat_anchor_day, calendar.monthrange(next_month.year, next_month.month)[1]))
		else:
			next_date = getdate(add_days(start, 1 if doc.repeat_pattern == "Daily" else 7))
		key = hashlib.sha256(f"{doc.series_key}:{next_date}".encode()).hexdigest()
		if (not doc.repeat_until or next_date <= getdate(doc.repeat_until)) and not frappe.db.exists(PREFIX + "Item", {"occurrence_key": key}):
			values = {field: doc.get(field) for field in ITEM_FIELDS - {"item_kind"}}
			values.update(space=doc.space, item_kind="Task", status="Open", owner=doc.owner, from_date=next_date,
				until_date=add_days(doc.until_date, (next_date - start).days) if doc.until_date else None,
				deadline=add_days(doc.deadline, (next_date - start).days) if doc.deadline else None,
				snoozed_until=None, series_key=doc.series_key, occurrence_key=key, repeat_anchor_day=doc.repeat_anchor_day)
			_insert("Item", values)
	_publish(doc.space, root)
	return _item_payload(doc, level)


@frappe.whitelist(methods=["POST"])
def record_progress(name, expected_modified, note, value=None, stage=None, outcome=None, effective_at=None, plan=None, attachments=None, request_key=None):
	doc, root, level = _item(name)
	if doc.item_kind != "Tracker":
		_deny()
	note = _text(note, 12000, True)
	uploads = _tracker_uploads(doc, attachments)
	key, fingerprint, prior = _tracker_request(doc, "progress", request_key,
		{"note": note, "value": value, "stage": stage, "outcome": outcome, "effective_at": effective_at, "plan": _json(plan, {}),
		 "files": [(filename, hashlib.sha256(content).hexdigest()) for filename, content in uploads]})
	if prior:
		return _item_payload(doc, level)
	_version(doc, expected_modified)
	stamp = get_datetime(effective_at) if effective_at else now_datetime()
	if stamp > now_datetime():
		frappe.throw(_("Progress cannot be dated in the future."))
	data = _json(doc.item_data, {})
	if value is not None:
		data["value"] = value
	if stage is not None:
		data["stage"] = stage
	if plan is not None:
		data.update(_data(plan, {"next_action", "attention_date", "attention_until"}))
	data = _tracker(data, root)
	if outcome and outcome not in {"Open", "Completed", "Failed"}:
		frappe.throw(_("Choose Open, Completed or Failed."))
	current = not doc.current_effective_at or stamp >= get_datetime(doc.current_effective_at)
	if current:
		doc.item_data = data
		doc.status = outcome or doc.status
		doc.current_effective_at = stamp
		_save(doc)
	entry = _entry(doc.space, note, kind="Progress", item=doc.name, request_key=key,
		snapshot={"title": doc.title, "effective_at": str(stamp), "item_data": data, "status": outcome or doc.status,
			"pending_with": _progress_pending_with(doc, data, outcome or doc.status), "request_fingerprint": fingerprint})
	for filename, content in uploads:
		_store_attachment(entry, filename, content)
	_publish(doc.space, root)
	return _item_payload(doc, level)



def _tracker_uploads(doc, attachments, required=False):
	values = _json(attachments, []) if isinstance(attachments, str) else [] if attachments is None else attachments
	if not isinstance(values, list) or len(values) > 5 or required and not values:
		frappe.throw(_("Choose one to five files, up to 10 MB each.") if required else _("Choose at most five attachments."))
	if values:
		# Item-only shares never grant access to the conversation's private evidence.
		_space(doc.space, write=True)
	prepared = []
	for row in values:
		value = _data(row, {"filename", "content"})
		prepared.append(_attachment_data(value.get("filename"), value.get("content")))
	return prepared


def _tracker_request(doc, operation, request_key, payload):
	if not request_key:
		if payload.get("files"):
			frappe.throw(_("A request key is required for file uploads. Reopen the form and try again."))
		return None, None, None
	key = _text(request_key, 100, True)
	key = hashlib.sha256(f"tracker:{frappe.session.user}:{doc.name}:{operation}:{key}".encode()).hexdigest()
	fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()
	existing = frappe.db.get_value(PREFIX + "Entry", {"request_key": key}, "name")
	prior = frappe.get_doc(PREFIX + "Entry", existing) if existing else None
	if prior and (prior.is_deleted or _json(prior.snapshot, {}).get("request_fingerprint") != fingerprint):
		frappe.throw(_("This upload was already submitted with different details. Reopen the form before making another update."))
	return key, fingerprint, prior


@frappe.whitelist(methods=["POST"])
def add_tracker_files(name, expected_modified, attachments, request_key, note=""):
	doc, root, level = _item(name)
	if doc.item_kind != "Tracker":
		_deny()
	_space(doc.space, write=True)
	uploads = _tracker_uploads(doc, attachments, required=True)
	note = _text(note, 12000)
	key, fingerprint, prior = _tracker_request(doc, "files", request_key,
		{"note": note, "files": [(filename, hashlib.sha256(content).hexdigest()) for filename, content in uploads]})
	if prior:
		return _item_payload(doc, level)
	_version(doc, expected_modified)
	_save(doc)  # Refresh Files/Updates without changing the tracker's progress or effective date.
	entry = _entry(doc.space, note or _("Added files to {0}").format(doc.title), kind="Note", item=doc.name,
		request_key=key, snapshot={"request_fingerprint": fingerprint})
	for filename, content in uploads:
		_store_attachment(entry, filename, content)
	_publish(doc.space, root)
	return _item_payload(doc, level)


@frappe.whitelist(methods=["POST"])
def get_tracker_files(name, before=None):
	doc, room, root, level = _read_item(name)
	if doc.item_kind != "Tracker":
		_deny()
	if not can_read_space(room.name):
		return {"files": [], "next_cursor": None, "can_add": False, "restricted": True}
	condition, params = "", [name]
	if before:
		anchor = frappe.db.sql("""select f.creation, f.name from `tabFile` f
			join `tabCollaboration Entry` e on f.attached_to_doctype='Collaboration Entry' and f.attached_to_name=e.name
			where f.name=%s and e.item=%s and e.is_deleted=0 and f.is_private=1""", [before, name], as_dict=True)
		if not anchor:
			_deny()
		condition = " and (f.creation < %s or (f.creation = %s and f.name < %s))"
		params.extend([anchor[0].creation, anchor[0].creation, anchor[0].name])
	rows = frappe.db.sql("""select f.name, f.file_name, f.file_url, f.file_size, f.creation,
		e.name as entry, e.entry_kind, e.body as note, e.owner as uploaded_by
		from `tabFile` f join `tabCollaboration Entry` e
		on f.attached_to_doctype='Collaboration Entry' and f.attached_to_name=e.name
		where e.item=%s and e.is_deleted=0 and f.is_private=1""" + condition +
		" order by f.creation desc, f.name desc limit 51", params, as_dict=True)
	files = [{**row, "uploaded_by_name": _name(row.uploaded_by)} for row in rows[:50]]
	return {"files": files, "next_cursor": rows[49].name if len(rows) > 50 else None,
		"can_add": level in {"Owner", "Manager", "Member"}, "restricted": False}


def _progress_pending_with(doc, config, status):
	if status not in OPEN:
		return None
	person = doc.assignee or doc.owner
	if config.get("assignment_mode") == "Stages":
		stages = config.get("stages", [])
		stage = next((row for row in stages if row["key"] == config.get("stage")), stages[0] if stages else {})
		person = stage.get("assignee")
	return {"user": person or "", "full_name": _name(person) if person else ""}


@frappe.whitelist(methods=["POST"])
def get_item_history(name):
	doc, room, _root, level = _read_item(name)
	rows = frappe.get_all(PREFIX + "Entry", filters={"item": name}, fields=["name"], order_by="creation desc", limit_page_length=100)
	history = [_entry_payload(frappe.get_doc(PREFIX + "Entry", row.name), level) for row in rows]
	if not can_read_space(room.name):
		for row in history:
			row.update(attachments=[], source_entry=None, can_edit=False, can_remove=False)
	return {"item": _item_payload(doc, level), "history": history}


@frappe.whitelist(methods=["POST"])
def get_my_work(date=None):
	user = _require()
	day = getdate(date or nowdate())
	rooms = frappe.get_all(PREFIX + "Space", filters={"root_space": ["in", _root_ids() or ["__none__"]], "archived": 0}, pluck="name", limit_page_length=0)
	rows = frappe.get_all(PREFIX + "Item", filters={"space": ["in", rooms or ["__none__"]]},
		fields=["name"], order_by="modified desc", limit_page_length=1000)
	seen = {row.name for row in rows}
	rows.extend(frappe._dict(name=name) for name in _shared_ids(user) if name not in seen)
	today, open_work, calendar, trackers = [], [], [], []
	for row in rows:
		doc, _room, root, level = _read_item(row.name)
		if root.archived or _room.archived:
			continue
		stage_users = {stage.get("assignee") for stage in _json(doc.item_data, {}).get("stages", [])} if doc.item_kind == "Tracker" else set()
		mine = doc.assignee == user or doc.owner == user or user in stage_users or bool(_share_level(doc, user))
		payload = _item_payload(doc, level)
		payload["space_title"] = _room.title
		if doc.item_kind == "Tracker" and mine:
			trackers.append(payload)
		if doc.item_kind in {"Task", "Tracker"} and doc.status in OPEN and mine:
			open_work.append(payload)
			plan = _json(doc.item_data, {})
			start = doc.from_date if doc.item_kind == "Task" else plan.get("attention_date")
			end = (doc.until_date or start) if doc.item_kind == "Task" else (plan.get("attention_until") or start)
			deadline_due = bool(doc.deadline and getdate(doc.deadline) <= day and day == getdate(nowdate()))
			if deadline_due or start and getdate(start) <= day and (not doc.snoozed_until or getdate(doc.snoozed_until) <= day) and (day == getdate(nowdate()) or day <= getdate(end)):
				today.append(payload)
		if doc.item_kind == "Event" and (not _json(doc.participants, []) or user in _json(doc.participants, [])):
			calendar.append(payload)
		elif doc.item_kind == "Task" and mine and doc.from_date:
			calendar.append(payload)
		elif doc.item_kind == "Tracker" and mine:
			plan = _json(doc.item_data, {})
			if plan.get("attention_date"):
				calendar.append({**payload, "from_date": plan["attention_date"], "until_date": plan.get("attention_until") or plan["attention_date"]})
	return {"date": str(day), "today": today, "open_progress": open_work, "calendar": calendar, "trackers": trackers,
		"has_more": len(rows) >= 1000}


def get_home_summary():
	"""Live Home reminders, recomputed against current membership; never email private chat."""
	user = _require()
	roots = _root_ids()
	spaces = frappe.get_all(PREFIX + "Space", filters={"root_space": ["in", roots or ["__none__"]], "archived": 0},
		fields=["name", "root_space"])
	archived_roots = set(frappe.get_all(PREFIX + "Space", filters={"name": ["in", roots or ["__none__"]], "archived": 1}, pluck="name"))
	ids = [s.name for s in spaces if s.root_space not in archived_roots]
	if not ids:
		return {"unread": 0, "due": 0}
	unread = frappe.db.sql("""select count(*) from `tabCollaboration Entry` e
		left join `tabCollaboration Read State` r on r.space=e.space and r.user=%s
		where e.space in %s and e.owner!=%s and e.is_deleted=0 and (r.read_at is null or e.creation>r.read_at)""",
		(user, ids, user))[0][0]
	items = frappe.get_all(PREFIX + "Item", filters={"space": ["in", ids], "item_kind": ["in", ["Task", "Tracker"]],
		"status": ["in", list(OPEN)]}, or_filters={"assignee": user, "owner": user},
		fields=["owner", "assignee", "item_kind", "from_date", "snoozed_until", "deadline", "item_data"], limit=0)
	due = 0
	for item in items:
		if item.assignee != user and (item.assignee or item.owner != user):
			continue
		start = item.from_date if item.item_kind == "Task" else _json(item.item_data, {}).get("attention_date")
		if (item.deadline and getdate(item.deadline) <= getdate(nowdate())) or (
			start and getdate(start) <= getdate(nowdate()) and (not item.snoozed_until or getdate(item.snoozed_until) <= getdate(nowdate()))):
			due += 1
	return {"unread": int(unread), "due": due}


def file_scoped(file):
	return file.attached_to_doctype == PREFIX + "Entry" and file.attached_to_name


def can_read_file(file, user=None):
	if not file_scoped(file) or not has_chat_access(user):
		return False
	entry = frappe.db.get_value(PREFIX + "Entry", file.attached_to_name, ["space", "is_deleted"], as_dict=True)
	return bool(entry and not entry.is_deleted and can_read_space(entry.space, user))


@frappe.whitelist(methods=["POST"])
def upload_attachment(entry, filename, content):
	doc = frappe.get_doc(PREFIX + "Entry", entry)
	_space(doc.space, write=True)
	if doc.owner != frappe.session.user or doc.is_deleted:
		_deny()
	filename, decoded = _attachment_data(filename, content)
	if frappe.db.count("File", {"attached_to_doctype": doc.doctype, "attached_to_name": doc.name}) >= 5:
		frappe.throw(_("Use at most five files per update."))
	return _store_attachment(doc, filename, decoded)


def _attachment_data(filename, content):
	filename = _text(filename, 180, True).replace("\\", "/").split("/")[-1]
	ext = filename.rsplit(".", 1)[-1].lower()
	if ext not in {"pdf", "png", "jpg", "jpeg", "gif", "webp", "txt", "csv", "docx", "xlsx"}:
		frappe.throw(_("Choose a PDF, image, text, Word or Excel file."))
	if not isinstance(content, str) or len(content) > 14 * 1024 * 1024:
		frappe.throw(_("Files must be 10 MB or smaller."))
	try:
		decoded = base64.b64decode(content, validate=True)
	except Exception:
		frappe.throw(_("Invalid file content."))
	if not decoded or len(decoded) > 10 * 1024 * 1024:
		frappe.throw(_("Use at most five non-empty files, up to 10 MB each."))
	if (ext == "pdf" and not decoded.startswith(b"%PDF-")) or (ext in {"docx", "xlsx"} and not decoded.startswith(b"PK")):
		frappe.throw(_("The file does not match its extension."))
	return filename, decoded


def _store_attachment(doc, filename, decoded):
	from frappe.utils.file_manager import save_file
	token = _writing_file.set(True)
	try:
		file = save_file(filename, decoded, doc.doctype, doc.name, is_private=1)
	finally:
		_writing_file.reset(token)
	return {"file_url": file.file_url, "file_name": file.file_name}


def validate_file_change(doc, method=None):
	old = doc.get_doc_before_save()
	if file_scoped(doc) or old and file_scoped(old):
		if not _writing_file.get() or not cint(doc.is_private):
			frappe.throw(_("Chat attachments are private and must be changed through chat."), frappe.PermissionError)


def can_read_space(name, user=None):
	if not has_chat_access(user):
		return False
	root = frappe.db.get_value(PREFIX + "Space", name, "root_space") or name
	return root in _root_ids(user)


def has_permission(doc, user=None, ptype=None, **kwargs):
	if ptype not in {"read", "select"} or not has_chat_access(user):
		return False
	if doc.doctype == PREFIX + "Space":
		return can_read_space(doc.name, user)
	if doc.doctype == PREFIX + "Member":
		return can_read_space(doc.parent, user)
	if doc.doctype == PREFIX + "Read State" and doc.user != (user or frappe.session.user):
		return False
	if doc.doctype == PREFIX + "Item" and doc.item_kind in {"Task", "Tracker"} and _share_level(doc, user):
		return True
	return can_read_space(doc.space, user)


def _query(doctype, user=None):
	ids = _root_ids(user)
	shared = _shared_ids(user) if doctype == "Item" else []
	if not ids and not shared:
		return "1=0"
	allowed = ",".join(frappe.db.escape(value) for value in ids) or "NULL"
	if doctype == "Space":
		return f"`tabCollaboration Space`.root_space in ({allowed})"
	if doctype == "Member":
		return f"`tabCollaboration Member`.parent in ({allowed})"
	query = f"`tabCollaboration {doctype}`.space in (select name from `tabCollaboration Space` where root_space in ({allowed}))"
	if shared:
		query = "(" + query + " or `tabCollaboration Item`.name in (" + ",".join(frappe.db.escape(value) for value in shared) + "))"
	if doctype == "Read State":
		query += " and `tabCollaboration Read State`.user=" + frappe.db.escape(user or frappe.session.user)
	return query


def space_query(user=None): return _query("Space", user)
def entry_query(user=None): return _query("Entry", user)
def item_query(user=None): return _query("Item", user)
def member_query(user=None): return _query("Member", user)
def read_query(user=None): return _query("Read State", user)
