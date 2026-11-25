"""Separate, installable SF Tasks client. Never grants Desk or ERP Home chat access."""
import json
import hashlib
from pathlib import Path

import frappe
from frappe.sessions import get_csrf_token
from werkzeug.wrappers import Response
from volunteering.volunteering.collaboration_access import has_app_chat_access
from volunteering.volunteering.collaboration_access import require_chat_access, chat_channel


@frappe.whitelist(allow_guest=True, methods=["GET"])
def get_session():
    frappe.local.response_headers["Cache-Control"] = "no-store, private"
    user = frappe.session.user
    return {"user": user if user != "Guest" else None, "allowed": has_app_chat_access(user),
            "full_name": frappe.db.get_value("User", user, "full_name") if user != "Guest" else "",
            "csrf_token": get_csrf_token(), "app_name": "SF Tasks PWA"}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def service_worker():
    root = Path(frappe.get_app_path("volunteering", "public", "sf_tasks"))
    manifest = json.loads((root / "build.json").read_text())
    entry = manifest["src/worker.js"]["file"]
    if not entry.startswith("assets/") or ".." in entry or not entry.endswith(".js"):
        frappe.throw("Invalid SF Tasks PWA build.")
    version = hashlib.sha256((root / "precache.json").read_bytes()).hexdigest()[:20]
    return Response('import "/assets/volunteering/sf_tasks/' + entry + '?v=' + version + '";',
                    content_type="text/javascript; charset=utf-8", headers={
                        "Service-Worker-Allowed": "/sf-tasks/", "Cache-Control": "no-cache, no-store",
                        "X-Content-Type-Options": "nosniff"})


@frappe.whitelist(methods=["POST"])
def get_work(date=None):
    """Personal work plus all trackers visible through chat membership or explicit shares."""
    require_chat_access("app")
    from volunteering.volunteering import collaboration as c
    token = chat_channel.set("app")
    try:
        result = c.get_my_work(date)
        rooms = frappe.get_all(c.PREFIX + "Space", filters={"root_space": ["in", c._root_ids() or ["__none__"]]}, pluck="name", limit_page_length=0)
        names = frappe.get_all(c.PREFIX + "Item", filters={"space": ["in", rooms or ["__none__"]], "item_kind": ["in", ["Task", "Tracker"]]}, pluck="name", order_by="modified desc", limit_page_length=1000)
        names = list(dict.fromkeys(names + c._shared_ids()))
        trackers, tasks = [], []
        for name in names:
            doc, room, root, level = c._read_item(name)
            if room.archived or root.archived:
                continue
            payload = dict(c._item_payload(doc, level), space_title=room.title)
            if doc.item_kind == "Tracker":
                trackers.append(payload)
            elif doc.owner == frappe.session.user or doc.assignee == frappe.session.user or c._share_level(doc) or any(row.get("assignee") == frappe.session.user for row in c._json(doc.item_data, {}).get("subtasks", [])):
                tasks.append(payload)
        return dict(result, trackers=trackers, tasks=tasks, has_more=result["has_more"] or len(names) >= 1000)
    finally:
        chat_channel.reset(token)


@frappe.whitelist(methods=["POST"])
def apply_operation(method, payload, request_key, expected_user):
    """A shared browser cookie must never send another account's durable Outbox."""
    user = require_chat_access("app")
    if user != expected_user:
        frappe.throw("Sign in to the original account before sending its saved changes.", frappe.PermissionError)
    from volunteering.volunteering.collaboration_mobile import apply_operation as operation
    return operation(method, payload, request_key)
