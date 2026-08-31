import frappe
from frappe import _

PROJECT_CONTROLLED_DOCTYPES = (
	"Purchase Order",
	"Purchase Invoice",
	"Expense Claim",
)
# Program cost objects — advances are not tagged to a project.
PROJECT_REQUIRED_DOCTYPES = ("Purchase Order", "Expense Claim")


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


def ensure_expense_claim_accounts(doc, method=None):
	"""Set GL accounts server-side so employees never need Account DocPerm."""
	if doc.doctype != "Expense Claim" or not doc.get("company"):
		return

	if not doc.get("payable_account"):
		doc.payable_account = _company_payable_account(doc.company)

	for row in doc.get("expenses") or []:
		if row.get("default_account") or not row.get("expense_type"):
			continue
		account = frappe.db.get_value(
			"Expense Claim Account",
			{"parent": row.expense_type, "company": doc.company},
			"default_account",
		)
		if account:
			row.default_account = account


def _company_payable_account(company: str) -> str | None:
	for fieldname in ("default_expense_claim_payable_account", "default_payable_account"):
		account = frappe.db.get_value("Company", company, fieldname)
		if account and frappe.db.get_value("Account", account, "account_type") == "Payable":
			return account
	return frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Payable", "is_group": 0, "disabled": 0},
		"name",
	)


def assign_department_from_owner(doc, method=None):
	if doc.doctype not in ("Purchase Order", "Purchase Invoice") or doc.get("department"):
		return

	employee = frappe.db.get_value("Employee", {"user_id": doc.owner}, "name")
	if not employee:
		return

	department = frappe.db.get_value("Employee", employee, "department")
	if department:
		doc.department = department


def validate_project_required(doc, method=None):
	if doc.doctype not in PROJECT_REQUIRED_DOCTYPES:
		return
	if doc.get("project"):
		return
	frappe.throw(
		_(
			"Set a Project on this {0} so spend is checked against the live department budget. "
			"Employee Advances are not tagged to a project; tag the Expense Claim when you settle."
		).format(doc.doctype)
	)


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
				_validate_advance_payment_account(doc, ea)
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


def _validate_advance_payment_account(payment_entry, employee_advance):
	"""Reject PE when paid_to is a customer Debtors / AR account (not Employee Advances)."""
	paid_to = payment_entry.get("paid_to") or employee_advance.get("advance_account")
	if not paid_to:
		return

	account = frappe.db.get_value(
		"Account",
		paid_to,
		["account_type", "account_name", "root_type"],
		as_dict=True,
	)
	if not account:
		return

	name_l = (account.account_name or "").lower()
	looks_like_debtors = "debtor" in name_l or "sundry debtor" in name_l
	is_receivable = account.account_type == "Receivable"

	# Correct setup: dedicated Employee Advances receivable (party = Employee).
	# Wrong setup: company Debtors / customer AR → GL throws "Customer is required".
	if is_receivable and looks_like_debtors:
		frappe.throw(
			_(
				"Payment Entry uses account {0}, which is a customer receivable (Debtors). "
				"Employee Advances must use the company's Employee Advances account "
				"(Receivable, party type Employee). Fix Company → Default Employee Advance Account "
				"and the Employee's Advance Account, then recreate the Payment Entry."
			).format(paid_to),
			title=_("Wrong Advance Account"),
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
