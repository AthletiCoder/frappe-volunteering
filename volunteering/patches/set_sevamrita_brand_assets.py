import frappe

LOGO = "/assets/volunteering/brand/logo-horizontal.png"
FAVICON = "/assets/volunteering/brand/icon-32.png"


def execute():
	"""Show the Sevamrita logo and favicon on Frappe's sign-in pages.

	Only fills empty values, so a logo an administrator already chose is kept.
	"""
	settings = frappe.get_single("Website Settings")
	changed = False
	if not settings.app_logo:
		settings.app_logo = LOGO
		changed = True
	if not settings.favicon:
		settings.favicon = FAVICON
		changed = True
	if changed:
		settings.flags.ignore_permissions = True
		settings.save()
