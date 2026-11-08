"""Native chat API. Both clients share data; each interface requires its own role."""
import frappe
from volunteering.volunteering import collaboration as c
from volunteering.volunteering.collaboration_access import chat_channel, require_chat_access


def _invoke(method, **kwargs):
	require_chat_access("app")
	token = chat_channel.set("app")
	try:
		return getattr(c, method)(**kwargs)
	finally:
		chat_channel.reset(token)


@frappe.whitelist(methods=["POST"])
def get_work_item(name):
	return _invoke("get_work_item", name=name)


@frappe.whitelist(methods=["POST"])
def share_item(name, shares, expected_modified):
	return _invoke("share_item", name=name, shares=shares, expected_modified=expected_modified)


@frappe.whitelist(methods=["POST"])
def get_directory(query=''):
	return _invoke("get_directory", query=query)


@frappe.whitelist(methods=["POST"])
def get_collaboration_home():
	return _invoke("get_collaboration_home", )


@frappe.whitelist(methods=["POST"])
def save_space(payload, name=None, expected_modified=None):
	return _invoke("save_space", payload=payload, name=name, expected_modified=expected_modified)


@frappe.whitelist(methods=["POST"])
def start_direct(user):
	return _invoke("start_direct", user=user)


@frappe.whitelist(methods=["POST"])
def get_space(name, before=None, item=None):
	return _invoke("get_space", name=name, before=before, item=item)


@frappe.whitelist(methods=["POST"])
def post_entry(space, body='', entry_kind='Message', request_key=None, source_entry=None):
	return _invoke("post_entry", space=space, body=body, entry_kind=entry_kind, request_key=request_key, source_entry=source_entry)


@frappe.whitelist(methods=["POST"])
def send_message(payload):
	return _invoke("send_message", payload=payload)


@frappe.whitelist(methods=["POST"])
def edit_entry(name, body=None, remove=False, expected_modified=None):
	return _invoke("edit_entry", name=name, body=body, remove=remove, expected_modified=expected_modified)


@frappe.whitelist(methods=["POST"])
def mark_read(space, entry):
	return _invoke("mark_read", space=space, entry=entry)


@frappe.whitelist(methods=["POST"])
def mark_delivered(space, entry):
	return _invoke("mark_delivered", space=space, entry=entry)


@frappe.whitelist(methods=["POST"])
def mark_seen(space, entry):
	return _invoke("mark_seen", space=space, entry=entry)


@frappe.whitelist(methods=["POST"])
def get_message_info(name):
	return _invoke("get_message_info", name=name)


@frappe.whitelist(methods=["POST"])
def save_item(space, payload, name=None, expected_modified=None):
	return _invoke("save_item", space=space, payload=payload, name=name, expected_modified=expected_modified)


@frappe.whitelist(methods=["POST"])
def update_task(name, action, expected_modified, date=None):
	return _invoke("update_task", name=name, action=action, expected_modified=expected_modified, date=date)


@frappe.whitelist(methods=["POST"])
def record_progress(name, expected_modified, note, value=None, stage=None, outcome=None, effective_at=None, plan=None, attachments=None, request_key=None):
	return _invoke("record_progress", name=name, expected_modified=expected_modified, note=note, value=value, stage=stage, outcome=outcome, effective_at=effective_at, plan=plan, attachments=attachments, request_key=request_key)


@frappe.whitelist(methods=["POST"])
def get_item_history(name):
	return _invoke("get_item_history", name=name)


@frappe.whitelist(methods=["POST"])
def get_my_work(date=None):
	return _invoke("get_my_work", date=date)


@frappe.whitelist(methods=["POST"])
def upload_attachment(entry, filename, content):
	return _invoke("upload_attachment", entry=entry, filename=filename, content=content)


@frappe.whitelist(methods=["POST"])
def get_reminders():
	require_chat_access("app")
	from volunteering.volunteering.collaboration_reminders import get_reminders as reminders
	token = chat_channel.set("app")
	try:
		return reminders()
	finally:
		chat_channel.reset(token)


@frappe.whitelist(methods=["POST"])
def add_tracker_files(name, expected_modified, attachments, request_key, note=""):
	return _invoke("add_tracker_files", name=name, expected_modified=expected_modified, attachments=attachments, request_key=request_key, note=note)


@frappe.whitelist(methods=["POST"])
def get_tracker_files(name, before=None):
	return _invoke("get_tracker_files", name=name, before=before)
