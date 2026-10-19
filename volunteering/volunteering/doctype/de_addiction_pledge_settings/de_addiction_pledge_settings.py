# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe import _
from frappe.model.document import Document

DEFAULT_CONFIRMATION_TEMPLATE = (
	"Thank you for taking the de-addiction pledge. "
	"Your pledge ID is {pledge_uuid}. People covered: {people_count}."
)


class DeAddictionPledgeSettings(Document):
	pass


def get_pledge_settings():
	"""Return De Addiction Pledge Settings; throws if API key is missing."""
	settings = frappe.get_single("De Addiction Pledge Settings")
	if not settings.get_password("api_key", raise_exception=False):
		frappe.throw(
			"De Addiction Pledge is not configured. Set API Key in De Addiction Pledge Settings.",
			title="De Addiction Pledge Settings",
		)
	return settings


def _assert_can_manage_settings():
	if frappe.session.user == "Administrator":
		return
	if "System Manager" in frappe.get_roles():
		return
	frappe.throw(_("Only System Managers can view the pledge API key."), frappe.PermissionError)


@frappe.whitelist()
def get_api_key():
	"""Return the stored API key for System Managers (Password fields are write-only in Desk)."""
	_assert_can_manage_settings()
	frappe.has_permission("De Addiction Pledge Settings", "read", throw=True)
	settings = frappe.get_single("De Addiction Pledge Settings")
	key = settings.get_password("api_key", raise_exception=False) or ""
	if not key:
		frappe.throw(_("API key is not set yet. Enter a key and save first."))
	return key
