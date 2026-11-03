"""Separate interface access from membership in shared collaboration data."""
from contextvars import ContextVar

import frappe
from frappe import _

WEB_ROLE = "Web chat access"
APP_ROLE = "App chat access"
CHAT_ROLES = (WEB_ROLE, APP_ROLE)
LEGACY_ROLE = "Chat access"
# Only the native API adapter sets this server-side context. Request headers and
# submitted fields cannot change which role a web endpoint requires.
chat_channel = ContextVar("chat_channel", default="web")


def has_role(user, role):
	user = user or frappe.session.user
	return bool(user and user != "Guest" and frappe.db.get_value("User", user, "enabled") and
		frappe.db.get_value("Role", role, "disabled") == 0 and
		frappe.db.exists("Has Role", {"parent": user, "parenttype": "User", "role": role}))


def has_web_chat_access(user=None):
	return has_role(user, WEB_ROLE)


def has_app_chat_access(user=None):
	return has_role(user, APP_ROLE)


def has_chat_access(user=None):
	"""Can participate, be assigned or receive a share through either interface."""
	return any(has_role(user, role) for role in CHAT_ROLES)


def require_chat_access(channel=None):
	channel = channel or chat_channel.get()
	role = APP_ROLE if channel == "app" else WEB_ROLE
	if not has_role(frappe.session.user, role):
		frappe.throw(_("{0} role is required.").format(role), frappe.PermissionError)
	return frappe.session.user
