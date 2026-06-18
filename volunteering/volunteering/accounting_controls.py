import frappe
from frappe import _

PROJECT_CONTROLLED_DOCTYPES = (
	"Purchase Order",
	"Purchase Invoice",
	"Expense Claim",
)


def set_cost_center_from_project(doc, method=None):
	if not doc.get("project"):
		return

	cost_center = frappe.db.get_value("Project", doc.project, "cost_center")
	if not cost_center:
		return

	doc.cost_center = cost_center
	if doc.doctype == "Expense Claim":
		for row in doc.get("expenses") or []:
			if not row.get("cost_center"):
				row.cost_center = cost_center


def validate_project_has_cost_center(doc, method=None):
	if doc.doctype not in PROJECT_CONTROLLED_DOCTYPES:
		return

	if not doc.get("project"):
		return

	cost_center = frappe.db.get_value("Project", doc.project, "cost_center")
	if not cost_center:
		frappe.throw(
			_(
				"Project {0} has no Cost Center. Set Cost Center on the Project before saving {1}."
			).format(doc.project, doc.doctype)
		)


def validate_purchase_invoice_po_chain(doc, method=None):
	if not doc.get("items"):
		frappe.throw(_("Purchase Invoice must have at least one item linked to a Purchase Order."))

	for row in doc.items:
		if not row.get("purchase_order"):
			frappe.throw(
				_("Row {0}: Every line must be linked to a Purchase Order.").format(row.idx)
			)

		po = frappe.get_doc("Purchase Order", row.purchase_order)

		if po.get("workflow_state") != "Approved":
			frappe.throw(
				_("Row {0}: Purchase Order {1} is not approved (current state: {2}).").format(
					row.idx,
					row.purchase_order,
					po.get("workflow_state") or _("not set"),
				)
			)

		if po.docstatus != 1:
			frappe.throw(
				_("Row {0}: Purchase Order {1} must be submitted before invoicing.").format(
					row.idx, row.purchase_order
				)
			)


def validate_payment_entry(doc, method=None):
	refs = doc.get("references") or []

	for ref in refs:
		if ref.reference_doctype == "Purchase Invoice":
			pi = frappe.get_doc("Purchase Invoice", ref.reference_name)
			if pi.get("workflow_state") != "Approved":
				frappe.throw(
					_("Payment not allowed. Invoice {0} is not approved.").format(pi.name)
				)

		if ref.reference_doctype == "Expense Claim":
			ec = frappe.get_doc("Expense Claim", ref.reference_name)
			if ec.get("workflow_state") != "Approved":
				frappe.throw(
					_("Payment not allowed. Expense Claim {0} is not approved.").format(ec.name)
				)

	if doc.party_type == "Employee":
		if not refs:
			frappe.throw(_("Reimbursement must be linked to an Expense Claim"))

		for ref in refs:
			if ref.reference_doctype != "Expense Claim":
				frappe.throw(
					_(
						"Employee payments must only reference Expense Claims (found {0})."
					).format(ref.reference_doctype)
				)

	if doc.party_type == "Supplier":
		if not refs:
			frappe.throw(_("Supplier payments must be linked to a Purchase Invoice"))

		for ref in refs:
			if ref.reference_doctype != "Purchase Invoice":
				frappe.throw(
					_(
						"Supplier payments must only reference Purchase Invoices (found {0})."
					).format(ref.reference_doctype)
				)
