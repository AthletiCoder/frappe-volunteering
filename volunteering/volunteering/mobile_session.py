"""Session bootstrap for the native Android client.

The app uses Frappe's normal password login and session cookie. A same-session
CSRF token is needed for the existing POST-only Home services; this endpoint
does not issue API keys or grant any additional permissions.
"""

import frappe
from frappe import _
from frappe.sessions import get_csrf_token


@frappe.whitelist(methods=["GET"])
def get_mobile_session():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in to use the Sevamrita app."), frappe.PermissionError)
	return {"user": user, "csrf_token": get_csrf_token()}
