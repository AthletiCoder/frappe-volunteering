"""Content-free FCM wake-ups. Message text is fetched only through a live ERP session.

No Firebase database, Functions or Analytics is used. Credentials stay in site config.
"""
import base64
import hashlib
import json
import re
import time
from datetime import timedelta

import frappe
import requests
from frappe.utils import now_datetime, get_datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from volunteering.volunteering.collaboration_access import has_app_chat_access, require_chat_access

DEVICE = "Collaboration Push Device"
OUTBOX = "Collaboration Push Outbox"
PACKAGES = {"org.sevamrita.mobile", "org.sevamrita.mobile.local"}
CONFIG = "sf_tasks_firebase"


def _config():
	return frappe.conf.get(CONFIG) or {}


def _save(doc):
	doc.flags.collaboration_write = True
	doc.save(ignore_permissions=True)
	return doc


@frappe.whitelist(methods=["POST"])
def get_push_config(package_name):
	require_chat_access("app")
	if package_name not in PACKAGES:
		frappe.throw("Unknown app package.")
	config = _config()
	app = config.get("apps", {}).get(package_name, {})
	enabled = bool(config.get("enabled") and config.get("project_id") and app.get("app_id") and app.get("api_key") and config.get("sender_id"))
	return {"enabled": enabled, **({"project_id": config["project_id"], "sender_id": config["sender_id"],
		"app_id": app["app_id"], "api_key": app["api_key"]} if enabled else {})}


@frappe.whitelist(methods=["POST"])
def register_device(installation, package_name, token, binding):
	user = require_chat_access("app")
	if not get_push_config(package_name)["enabled"]:
		return {"registered": False}
	if not re.fullmatch(r"[a-f0-9-]{36}", str(installation)) or not re.fullmatch(r"[a-f0-9]{64}", str(binding)):
		frappe.throw("Invalid installation identity.")
	if not isinstance(token, str) or not 20 <= len(token) <= 4096 or any(c.isspace() for c in token):
		frappe.throw("Invalid notification registration.")
	name = hashlib.sha256(f"{package_name}:{installation}".encode()).hexdigest()
	fingerprint = hashlib.sha256(token.encode()).hexdigest()
	# A rotated/reinstalled device token must not remain bound to two users.
	frappe.db.set_value(DEVICE, {"token_key": fingerprint}, "enabled", 0, update_modified=False)
	doc = frappe.get_doc(DEVICE, name, for_update=True) if frappe.db.exists(DEVICE, name) else frappe.new_doc(DEVICE)
	doc.name = name
	doc.flags.name_set = True
	doc.update({"user": user, "installation": installation, "package_name": package_name, "token": token,
		"token_key": fingerprint, "binding": binding, "enabled": 1, "last_registered": now_datetime()})
	_save(doc)
	return {"registered": True}


@frappe.whitelist(methods=["POST"])
def unregister_device(installation, package_name):
	user = require_chat_access("app")
	frappe.db.set_value(DEVICE, {"installation": installation, "package_name": package_name, "user": user}, "enabled", 0)
	return {"unregistered": True}


@frappe.whitelist(methods=["POST"])
def get_notification_entry(name):
	"""Revalidate current membership, role, deletion and read state on the receiving phone."""
	user = require_chat_access("app")
	from volunteering.volunteering import collaboration as c
	doc = frappe.get_doc("Collaboration Entry", name)
	if not c.can_read_space(doc.space, user) or doc.is_deleted or doc.owner == user or doc.entry_kind == "System" and user not in c._json(doc.snapshot, {}).get("notify_users", []):
		return {"notify": False}
	seen = frappe.db.get_value("Collaboration Read State", {"space": doc.space, "user": user}, "seen_through")
	if seen and get_datetime(seen) >= get_datetime(doc.creation):
		return {"notify": False}
	room = frappe.get_doc("Collaboration Space", doc.space)
	root = frappe.get_doc("Collaboration Space", room.root_space or room.name)
	if root.archived or room.archived:
		return {"notify": False}
	return {"notify": True, "entry": doc.name, "space": room.name, "title": room.title,
		"sender": c._name(doc.owner), "body": c._entry_payload(doc, "Viewer")["body"][:400], "mentioned": user in c._json(doc.get("mentions"), []), "assigned": user in c._json(doc.snapshot, {}).get("notify_users", []), "created_at": str(doc.creation)}


def queue_entry(doc, method=None):
	if not _config().get("enabled") or doc.is_deleted:
		return
	from volunteering.volunteering import collaboration as c
	room = frappe.get_doc("Collaboration Space", doc.space)
	root = frappe.get_doc("Collaboration Space", room.root_space or room.name)
	users = [row.user for row in root.members if row.user != doc.owner and has_app_chat_access(row.user)]
	if doc.entry_kind == "System":
		users = [uid for uid in users if uid in c._json(doc.snapshot, {}).get("notify_users", [])]
	if not users:
		return
	# Capture device/session membership now: users added later do not receive old pushes.
	recipients = frappe.get_all(DEVICE, filters={"user": ["in", users], "enabled": 1}, fields=["name", "binding"])
	if not recipients:
		return
	name = hashlib.sha256(doc.name.encode()).hexdigest()
	outbox = frappe.new_doc(OUTBOX)
	outbox.update({"name": name, "entry": doc.name, "recipients": json.dumps(recipients),
		"status": "Pending", "attempts": 0, "next_attempt": now_datetime()})
	outbox.flags.name_set = True
	_save(outbox)
	frappe.enqueue(deliver_outbox, name=name, enqueue_after_commit=True)


def flush_pending():
	if not _config().get("enabled"):
		return
	for name in frappe.get_all(OUTBOX, filters={"status": "Pending", "next_attempt": ["<=", now_datetime()]}, pluck="name", limit_page_length=100):
		frappe.enqueue(deliver_outbox, name=name, job_id=f"chat-push:{name}", deduplicate=True)


def deliver_outbox(name):
	if not _config().get("enabled"):
		return
	doc = frappe.get_doc(OUTBOX, name, for_update=True)
	if doc.status != "Pending":
		return
	entry = frappe.get_doc("Collaboration Entry", doc.entry)
	from volunteering.volunteering import collaboration as c
	if entry.is_deleted or get_datetime(entry.creation) < now_datetime() - timedelta(hours=24):
		doc.status = "Skipped"; _save(doc); return
	recipients = json.loads(doc.recipients)
	# Bound network time per worker job; continue larger groups after commit.
	remaining = recipients[10:]
	exhausted = doc.last_error == "delivery_failed"
	for recipient in recipients[:10]:
		device = frappe.get_doc(DEVICE, recipient["name"])
		if not device.enabled or device.binding != recipient["binding"] or device.user == entry.owner or not has_app_chat_access(device.user) or not c.can_read_space(entry.space, device.user):
			continue
		seen = frappe.db.get_value("Collaboration Read State", {"space": entry.space, "user": device.user}, "seen_through")
		if seen and get_datetime(seen) >= get_datetime(entry.creation):
			continue
		try:
			status = _send(device, entry)
		except (requests.RequestException, ValueError, KeyError, TypeError):
			status = "retry"
		if status == "invalid":
			device.enabled = 0; _save(device)
		elif status != "sent":
			attempts = recipient.get("attempts", 0) + 1
			if attempts < 6:
				remaining.append({**recipient, "attempts": attempts})
			else:
				exhausted = True
	doc.attempts += 1
	doc.recipients = json.dumps(remaining)
	doc.status = "Pending" if remaining else "Failed" if exhausted else "Sent"
	doc.last_error = "delivery_failed" if exhausted else "delivery_retry" if remaining else ""
	doc.next_attempt = now_datetime() + timedelta(minutes=min(60, 2 ** max((row.get("attempts", 0) for row in remaining), default=0)))
	_save(doc)
	if len(recipients) > 10:
		frappe.enqueue(deliver_outbox, name=doc.name, enqueue_after_commit=True)


def _send(device, entry):
	project = _config()["project_id"]
	if not re.fullmatch(r"[a-z][a-z0-9-]{4,62}", project):
		raise ValueError("Invalid Firebase project")
	# No body, author, title, attachment, credential or email is sent through Google.
	response = requests.post(f"https://fcm.googleapis.com/v1/projects/{project}/messages:send",
		headers={"Authorization": f"Bearer {_access_token()}"}, json={"message": {
			"token": device.get_password("token"), "data": {"entry": entry.name, "binding": device.binding},
			"android": {"priority": "HIGH", "ttl": "86400s"}}}, timeout=(5, 15))
	if response.status_code == 200:
		return "sent"
	if response.status_code == 404 and any(d.get("errorCode") == "UNREGISTERED" for d in response.json().get("error", {}).get("details", [])):
		return "invalid"
	if response.status_code == 401:
		frappe.cache.delete_value("sf_tasks_fcm_access_token")
	return "retry"


def _access_token():
	cached = frappe.cache.get_value("sf_tasks_fcm_access_token")
	if cached:
		return cached
	credentials = _config()["service_account"]
	if isinstance(credentials, str):
		credentials = json.loads(credentials)
	if credentials["project_id"] != _config()["project_id"]:
		raise ValueError("Firebase service account project mismatch")
	def b64(data):
		return base64.urlsafe_b64encode(data).rstrip(b"=")
	stamp = int(time.time())
	claim = {"iss": credentials["client_email"], "scope": "https://www.googleapis.com/auth/firebase.messaging",
		"aud": "https://oauth2.googleapis.com/token", "iat": stamp, "exp": stamp + 3600}
	signing_input = b".".join(b64(json.dumps(part, separators=(",", ":")).encode()) for part in ({"alg": "RS256", "typ": "JWT"}, claim))
	key = serialization.load_pem_private_key(credentials["private_key"].encode(), password=None)
	assertion = (signing_input + b"." + b64(key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256()))).decode()
	response = requests.post("https://oauth2.googleapis.com/token", data={
		"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}, timeout=(5, 15))
	response.raise_for_status()
	token = response.json()["access_token"]
	frappe.cache.set_value("sf_tasks_fcm_access_token", token, expires_in_sec=3000)
	return token
