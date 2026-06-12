import frappe
from frappe.model.document import Document


class VolunteeringAccountingSettings(Document):
	pass


def get_accounting_settings():
	"""Return accounting settings with defaults if not yet created."""
	if frappe.db.exists("DocType", "Volunteering Accounting Settings"):
		return frappe.get_cached_doc("Volunteering Accounting Settings")
	return frappe._dict(tier_1_limit=2000, tier_2_limit=10000)
