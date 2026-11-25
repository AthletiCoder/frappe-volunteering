"""Standard Web Push for the separate PWA; no Firebase or native app changes.

Subscriptions are encrypted Password fields. VAPID identity is derived from the
site's private encryption key with domain separation; no private key is public.
"""
import base64
import hashlib
import hmac
import json
import re
from datetime import timedelta
from urllib.parse import urlsplit

import frappe
import requests
from frappe.utils import get_datetime, now_datetime, get_system_timezone
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from volunteering.volunteering.collaboration_access import require_chat_access, has_app_chat_access, chat_channel

DEVICE = "SF Tasks Web Subscription"
NOTICE = "SF Tasks Web Notification"
PUSH_HOSTS = {"fcm.googleapis.com", "updates.push.services.mozilla.com", "web.push.apple.com"}
CURVE_ORDER = 0xffffffff00000000ffffffffffffffffbce6faada7179e84f3b9cac2fc632551


def _save(doc):
    doc.flags.collaboration_write = True
    return doc.save(ignore_permissions=True)


def _b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def _identity():
    secret = frappe.conf.get("encryption_key")
    if not secret:
        frappe.throw("This site needs its encryption key before notifications can be enabled.")
    value = int.from_bytes(hmac.new(secret.encode(), b"sf-tasks-pwa-vapid-v1", hashlib.sha256).digest(), "big")
    key = ec.derive_private_key(value % (CURVE_ORDER - 1) + 1, ec.SECP256R1())
    return key


@frappe.whitelist(methods=["POST"])
def get_config():
    require_chat_access("app")
    return {"public_key": _b64(_identity().public_key().public_bytes(serialization.Encoding.X962,
        serialization.PublicFormat.UncompressedPoint)), "enabled": not frappe.conf.get("sf_tasks_pwa_disable_push", False)}


def clean_subscription(subscription):
    value = frappe.parse_json(subscription) if isinstance(subscription, str) else subscription
    if not isinstance(value, dict) or not isinstance(value.get("keys"), dict):
        frappe.throw("Invalid browser notification subscription.")
    endpoint = value.get("endpoint", "")
    if not isinstance(endpoint, str):
        frappe.throw("Invalid browser notification endpoint.")
    parsed = urlsplit(endpoint)
    # Prevent requests to arbitrary user-supplied URLs, local services or redirects.
    try:
        port = parsed.port
    except ValueError:
        frappe.throw("Choose a supported browser push service.")
    allowed = parsed.hostname in PUSH_HOSTS or bool(parsed.hostname and parsed.hostname.endswith(".notify.windows.com"))
    if parsed.scheme != "https" or not allowed or parsed.username or parsed.password or port not in (None, 443) or parsed.fragment or not 20 <= len(endpoint) <= 4096:
        frappe.throw("Choose a supported browser push service.")
    keys = value["keys"]
    try:
        public = base64.urlsafe_b64decode(keys["p256dh"] + "=" * (-len(keys["p256dh"]) % 4))
        auth = base64.urlsafe_b64decode(keys["auth"] + "=" * (-len(keys["auth"]) % 4))
        if len(auth) != 16:
            raise ValueError
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), public)
    except (ValueError, KeyError, TypeError):
        frappe.throw("Invalid browser notification keys.")
    return {"endpoint": endpoint, "keys": {"auth": keys["auth"], "p256dh": keys["p256dh"]}}


def clean_preferences(value):
    value = frappe.parse_json(value) if isinstance(value, str) else value
    value = value or {}
    if not isinstance(value, dict):
        frappe.throw("Invalid notification preferences.")
    if value.get("mode", "All") not in {"All", "Mentions", "Mute"}:
        frappe.throw("Choose a notification mode.")
    result = {"mode": value.get("mode", "All")}
    for key in ("quiet_from", "quiet_until"):
        text = value.get(key) or ""
        if text and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", text):
            frappe.throw("Choose a valid quiet-hours time.")
        result[key] = text
    chats = value.get("chats") or {}
    if not isinstance(chats, dict) or len(chats) > 300 or any(mode not in {"All", "Mentions", "Mute"} for mode in chats.values()):
        frappe.throw("Invalid conversation notification settings.")
    result["chats"] = chats
    return result


@frappe.whitelist(methods=["POST"])
def subscribe(subscription, binding, preferences=None):
    user = require_chat_access("app")
    if not get_config()["enabled"]:
        frappe.throw("Web notifications are disabled on this site.")
    if not re.fullmatch(r"[a-f0-9-]{36}", binding):
        frappe.throw("Invalid browser identity.")
    clean = clean_subscription(subscription)
    name = hashlib.sha256(clean["endpoint"].encode()).hexdigest()
    exists = frappe.db.exists(DEVICE, name)
    if not exists and frappe.db.count(DEVICE, {"user": user, "enabled": 1}) >= 10:
        frappe.throw("At most ten browsers can receive notifications for this account. Disable an older subscription first.")
    doc = frappe.get_doc(DEVICE, name, for_update=True) if exists else frappe.new_doc(DEVICE)
    doc.name = name
    doc.flags.name_set = True
    doc.update({"user": user, "subscription": json.dumps(clean), "binding": binding, "enabled": 1,
                "preferences": json.dumps(clean_preferences(preferences))})
    _save(doc)
    return {"registered": True}


@frappe.whitelist(methods=["POST"])
def unsubscribe(binding):
    user = require_chat_access("app")
    frappe.db.set_value(DEVICE, {"user": user, "binding": binding}, "enabled", 0)
    return {"unregistered": True}


def _notice(device, key, data):
    name = hashlib.sha256(f"{device.name}:{device.binding}:{key}".encode()).hexdigest()
    if not frappe.db.exists(NOTICE, name):
        doc = frappe.new_doc(NOTICE)
        doc.name = name
        doc.flags.name_set = True
        doc.update({"device": device.name, "binding": device.binding, "data": json.dumps(data), "status": "Pending", "attempts": 0, "next_attempt": now_datetime()})
        _save(doc)
        frappe.enqueue(deliver, name=name, job_id=f"sf-pwa-push:{name}", deduplicate=True, enqueue_after_commit=True)


def queue_entry(doc, method=None):
    if frappe.conf.get("sf_tasks_pwa_disable_push") or doc.is_deleted or not frappe.db.table_exists(DEVICE):
        return
    from volunteering.volunteering import collaboration as c
    room = frappe.get_doc(c.PREFIX + "Space", doc.space)
    root = frappe.get_doc(c.PREFIX + "Space", room.root_space or room.name)
    users = [row.user for row in root.members if row.user != doc.owner and has_app_chat_access(row.user)]
    assigned = c._json(doc.snapshot, {}).get("notify_users", [])
    if doc.entry_kind == "System":
        users = [user for user in users if user in assigned]
    for device in frappe.get_all(DEVICE, filters={"user": ["in", users or ["__none__"]], "enabled": 1}, fields=["name", "binding", "user"]):
        _notice(device, doc.name, {"kind": "message", "key": doc.name, "entry": doc.name, "space": doc.space,
            "mentioned": device.user in c._json(doc.mentions, []), "assigned": device.user in assigned})


def _quiet_end(preferences, stamp):
    start, end = preferences.get("quiet_from"), preferences.get("quiet_until")
    if not start or not end or start == end:
        return None
    clock = stamp.strftime("%H:%M")
    quiet = start <= clock < end if start < end else clock >= start or clock < end
    if not quiet:
        return None
    hour, minute = map(int, end.split(":"))
    result = stamp.replace(hour=hour, minute=minute, second=0, microsecond=0)
    return result + timedelta(days=1) if result <= stamp else result


def flush_pending():
    if frappe.conf.get("sf_tasks_pwa_disable_push") or not frappe.db.table_exists(DEVICE):
        return
    from volunteering.volunteering import collaboration as c
    from volunteering.volunteering.collaboration_reminders import get_reminders
    # Generate each scheduled reminder once. Do not dump older overdue reminders on launch.
    for user in set(frappe.get_all(DEVICE, filters={"enabled": 1}, pluck="user", limit_page_length=1000)):
        if not has_app_chat_access(user):
            continue
        original_user = frappe.session.user
        token = chat_channel.set("app")
        try:
            frappe.set_user(user)
            reminders = get_reminders()["reminders"]
        finally:
            frappe.set_user(original_user)
            chat_channel.reset(token)
        from zoneinfo import ZoneInfo
        stamp = now_datetime().replace(tzinfo=ZoneInfo(get_system_timezone())).timestamp() * 1000
        for reminder in reminders:
            if 0 <= stamp - reminder["timestamp_ms"] < 300000:
                for device in frappe.get_all(DEVICE, filters={"user": user, "enabled": 1}, fields=["name", "binding"]):
                    _notice(device, reminder["key"], {"kind": "reminder", "key": reminder["key"], "space": reminder["space"], "item": reminder["item"]})
    for name in frappe.get_all(NOTICE, filters={"status": "Pending", "next_attempt": ["<=", now_datetime()]}, pluck="name", limit_page_length=100):
        frappe.enqueue(deliver, name=name, job_id=f"sf-pwa-push:{name}", deduplicate=True, enqueue_after_commit=True)


def deliver(name):
    from pywebpush import webpush, WebPushException
    from volunteering.volunteering import collaboration as c
    doc = frappe.get_doc(NOTICE, name, for_update=True)
    if doc.status != "Pending":
        return
    device = frappe.get_doc(DEVICE, doc.device)
    payload = frappe.parse_json(doc.data)
    valid = device.enabled and device.binding == doc.binding and has_app_chat_access(device.user) and c.can_read_space(payload["space"], device.user)
    if payload["kind"] == "message" and valid:
        entry = frappe.get_doc(c.PREFIX + "Entry", payload["entry"])
        seen = frappe.db.get_value(c.PREFIX + "Read State", {"space": entry.space, "user": device.user}, "seen_through")
        valid = not entry.is_deleted and not (seen and get_datetime(seen) >= entry.creation)
    if payload["kind"] == "reminder" and valid:
        item = frappe.get_doc(c.PREFIX + "Item", payload["item"])
        from volunteering.volunteering.collaboration_reminders import events_for
        valid = item.status in c.OPEN and any(row["key"] == payload["key"] for row in events_for(item, device.user, now_datetime(), get_system_timezone()))
    preferences = frappe.parse_json(device.preferences or "{}")
    mode = preferences.get("chats", {}).get(payload["space"], preferences.get("mode", "All"))
    if not valid or mode == "Mute" or payload["kind"] == "message" and mode == "Mentions" and not payload.get("mentioned") and not payload.get("assigned") or doc.creation < now_datetime() - timedelta(hours=24):
        doc.status = "Skipped"
        _save(doc)
        return
    quiet_end = _quiet_end(preferences, now_datetime())
    if quiet_end:
        doc.next_attempt = quiet_end
        _save(doc)
        return
    key = _identity().private_bytes(serialization.Encoding.DER, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption())
    try:
        webpush(subscription_info=json.loads(device.get_password("subscription")),
                data=json.dumps({**payload, "binding": device.binding}), vapid_private_key=_b64(key),
                vapid_claims={"sub": frappe.conf.get("sf_tasks_pwa_push_contact") or "https://sevamrita.org"},
                ttl=86400, timeout=10, headers={"Urgency": "normal"})
        doc.status = "Sent"
    except (WebPushException, requests.RequestException, ValueError) as error:
        response = getattr(error, "response", None)
        status = response.status_code if response is not None else None
        if status in {404, 410}:
            device.enabled = 0
            _save(device)
            doc.status = "Skipped"
        else:
            doc.attempts += 1
            doc.status = "Failed" if doc.attempts >= 6 else "Pending"
            doc.next_attempt = now_datetime() + timedelta(minutes=min(60, 2 ** doc.attempts))
    _save(doc)
