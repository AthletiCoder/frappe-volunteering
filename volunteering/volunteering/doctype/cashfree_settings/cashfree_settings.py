import frappe
from frappe.model.document import Document


class CashfreeSettings(Document):
	def validate(self):
		if self.min_amount is not None and self.min_amount < 0:
			frappe.throw("Minimum amount cannot be negative")
		if self.max_amount_per_txn and self.min_amount and self.max_amount_per_txn < self.min_amount:
			frappe.throw("Max amount per transaction must be >= minimum amount")


def get_cashfree_settings():
	"""Return Cashfree Settings singleton; throws if credentials missing."""
	settings = frappe.get_single("Cashfree Settings")
	if not settings.app_id or not settings.get_password("secret_key", raise_exception=False):
		frappe.throw(
			"Cashfree is not configured. Set App ID and Secret Key in Cashfree Settings.",
			title="Cashfree Settings",
		)
	return settings
