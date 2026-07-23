import frappe
from frappe import _

PROJECT_CONTROLLED_DOCTYPES = (
	"Purchase Order",
	"Purchase Invoice",
	"Expense Claim",
	"Employee Advance",
)


def set_cost_center_from_project(doc, method=None):
	if not doc.get("project"):
		return

	cost_center = frappe.db.get_value("Project", doc.project, "cost_center")
	if not cost_center:
		return

	meta = frappe.get_meta(doc.doctype)
	if meta.has_field("cost_center"):
		doc.cost_center = cost_center
	if doc.doctype == "Expense Claim":
		for row in doc.get("expenses") or []:
			if not row.get("cost_center"):
				row.cost_center = cost_center


def assign_department_from_employee(doc, method=None):
	if doc.doctype != "Expense Claim" or not doc.get("employee"):
		return
	if doc.get("department"):
		return

	department = frappe.db.get_value("Employee", doc.employee, "department")
	if department:
		doc.department = department


def assign_department_from_owner(doc, method=None):
	if doc.doctype not in ("Purchase Order", "Purchase Invoice") or doc.get("department"):
		return

	employee = frappe.db.get_value("Employee", {"user_id": doc.owner}, "name")
	if not employee:
		return

	department = frappe.db.get_value("Employee", employee, "department")
	if department:
		doc.department = department


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
			if pi.get("workflow_state") and pi.get("workflow_state") != "Approved":
				frappe.throw(
					_("Payment not allowed. Invoice {0} is not approved.").format(pi.name)
				)
		elif ref.reference_doctype == "Purchase Order":
			po = frappe.get_doc("Purchase Order", ref.reference_name)
			if po.get("workflow_state") and po.get("workflow_state") != "Approved":
				frappe.throw(
					_("Payment not allowed. Purchase Order {0} is not approved.").format(po.name)
				)
			if po.docstatus != 1:
				frappe.throw(
					_("Payment not allowed. Purchase Order {0} must be submitted.").format(po.name)
				)

	if doc.party_type == "Employee":
		if not refs:
			frappe.throw(
				_("Employee payments must be linked to an Expense Claim or Employee Advance.")
			)

		for ref in refs:
			if ref.reference_doctype == "Expense Claim":
				ec = frappe.get_doc("Expense Claim", ref.reference_name)
				if ec.get("workflow_state") and ec.get("workflow_state") != "Approved":
					frappe.throw(
						_("Payment not allowed. Expense Claim {0} is not approved.").format(ec.name)
					)
			elif ref.reference_doctype == "Employee Advance":
				ea = frappe.get_doc("Employee Advance", ref.reference_name)
				if ea.get("workflow_state") and ea.get("workflow_state") != "Approved":
					frappe.throw(
						_("Payment not allowed. Employee Advance {0} is not approved.").format(
							ea.name
						)
					)
				_warn_prior_advance_residuals(ea)
			else:
				frappe.throw(
					_(
						"Employee payments must only reference Expense Claims or Employee Advances "
						"(found {0})."
					).format(ref.reference_doctype)
				)

	if doc.party_type == "Supplier":
		if not refs:
			frappe.throw(
				_("Supplier payments must be linked to a Purchase Invoice or Purchase Order.")
			)

		for ref in refs:
			if ref.reference_doctype not in ("Purchase Invoice", "Purchase Order"):
				frappe.throw(
					_(
						"Supplier payments must only reference Purchase Invoices or Purchase Orders "
						"(found {0})."
					).format(ref.reference_doctype)
				)


def _warn_prior_advance_residuals(employee_advance):
	"""Soft warning when paying a new advance while prior residuals remain."""
	from volunteering.volunteering.employee_advance_controls import residual_advances_for_employee

	employee = employee_advance.get("employee")
	if not employee:
		return

	residuals = [
		r
		for r in residual_advances_for_employee(employee)
		if r.get("name") != employee_advance.get("name")
	]
	if not residuals:
		return

	parts = [
		_("{0}: {1}").format(r["name"], frappe.format_value(r["residual"], "Currency"))
		for r in residuals
	]
	frappe.msgprint(
		_(
			"This employee still has residual on prior advance(s): {0}. "
			"Chase claim or return before or alongside this top-up."
		).format("; ".join(parts)),
		title=_("Prior Advance Residual"),
		indicator="orange",
	)
