import frappe

ACCOUNTING_SERVER_SCRIPTS = (
	"Cost Center for PO",
	"Block Payment without Invoice",
	"Mandatory PO for PI",
)


def execute():
	for name in ACCOUNTING_SERVER_SCRIPTS:
		if frappe.db.exists("Server Script", name):
			frappe.db.set_value("Server Script", name, "disabled", 1)
