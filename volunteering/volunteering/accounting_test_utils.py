from contextlib import ExitStack
from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate


def mute_accounting_test_emails():
	"""Block workflow-action PDF emails (wkhtmltopdf) and frappe.sendmail in tests.

	`frappe.flags.mute_emails` / patching sendmail is not enough: Workflow Action
	builds the mail with attach_print() before send, and that blows up under
	frappe.in_test (enqueue runs inline).
	"""
	frappe.flags.mute_emails = True
	stack = ExitStack()
	stack.enter_context(patch("frappe.sendmail"))
	stack.enter_context(
		patch(
			"frappe.workflow.doctype.workflow_action.workflow_action.send_workflow_action_email",
			lambda *args, **kwargs: None,
		)
	)
	return stack


def get_or_create_user(email, roles, first_name="Test"):
	if frappe.db.exists("User", email):
		user = frappe.get_doc("User", email)
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"send_welcome_email": 0,
				"new_password": "password",
			}
		)
		user.insert(ignore_permissions=True)

	existing_roles = {row.role for row in user.roles}
	for role in roles:
		if role not in existing_roles:
			user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	return email


def get_or_create_department(name, department_head=None):
	company = frappe.db.get_value("Company", {}, "name")
	filters = {"department_name": name}
	if company:
		filters["company"] = company

	existing = frappe.db.get_value("Department", filters, "name")
	if existing:
		if (
			department_head
			and frappe.db.get_value("Department", existing, "department_head") != department_head
		):
			frappe.db.set_value("Department", existing, "department_head", department_head)
		return existing

	doc = {"doctype": "Department", "department_name": name}
	if company:
		doc["company"] = company
	if department_head:
		doc["department_head"] = department_head
	return frappe.get_doc(doc).insert(ignore_permissions=True).name


def get_or_create_employee(user_email, department, first_name="Test Employee"):
	employee = frappe.db.get_value("Employee", {"user_id": user_email}, "name")
	if employee:
		frappe.db.set_value("Employee", employee, "department", department)
		return employee

	company = frappe.db.get_value("Company", {}, "name")
	return (
		frappe.get_doc(
			{
				"doctype": "Employee",
				"first_name": first_name,
				"company": company,
				"user_id": user_email,
				"company_email": user_email,
				"department": department,
				"status": "Active",
				"date_of_birth": add_days(nowdate(), -10000),
				"date_of_joining": add_days(nowdate(), -90),
				"gender": "Male",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def ensure_employee_grade(grade):
	if not frappe.db.exists("Employee Grade", grade):
		frappe.get_doc({"doctype": "Employee Grade", "__newname": grade}).insert(ignore_permissions=True)
	return grade


def set_employee_grade(employee, grade, reports_to=None):
	"""Grade carries approval / advance limits; designation stays the job title."""
	ensure_employee_grade(grade)
	values = {"grade": grade}
	if reports_to is not None:
		values["reports_to"] = reports_to
	frappe.db.set_value("Employee", employee, values)
	return grade


def get_or_create_project_with_cost_center():
	project_name = "_Test Accounting Project"
	existing = frappe.db.get_value("Project", {"project_name": project_name}, "name")
	if existing:
		if not frappe.db.get_value("Project", existing, "cost_center"):
			cost_center = get_or_create_cost_center()
			frappe.db.set_value("Project", existing, "cost_center", cost_center)
		return existing

	company = frappe.db.get_value("Company", {}, "name")
	cost_center = get_or_create_cost_center()
	return (
		frappe.get_doc(
			{
				"doctype": "Project",
				"project_name": project_name,
				"company": company,
				"cost_center": cost_center,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def _get_parent_cost_center(company):
	parent = frappe.db.get_value(
		"Cost Center",
		{"company": company, "is_group": 1, "parent_cost_center": ["is", "not set"]},
		"name",
	)
	if parent:
		return parent

	abbr = frappe.db.get_value("Company", company, "abbr")
	for candidate in filter(None, (f"{abbr} - {abbr}" if abbr else None, company)):
		if frappe.db.exists("Cost Center", candidate):
			return candidate

	return frappe.db.get_value("Cost Center", {"company": company, "is_group": 1}, "name")


def get_or_create_cost_center():
	company = frappe.db.get_value("Company", {}, "name")
	abbr = frappe.db.get_value("Company", company, "abbr") or "TC"
	name = f"_Test Accounting - {abbr}"
	if frappe.db.exists("Cost Center", name):
		return name

	existing_leaf = frappe.db.get_value("Cost Center", {"company": company, "is_group": 0}, "name")
	if existing_leaf:
		return existing_leaf

	parent_cost_center = _get_parent_cost_center(company)
	if not parent_cost_center:
		frappe.throw(f"No parent Cost Center found for company {company}")

	return (
		frappe.get_doc(
			{
				"doctype": "Cost Center",
				"cost_center_name": "_Test Accounting",
				"company": company,
				"parent_cost_center": parent_cost_center,
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def get_or_create_payable_account(company=None):
	company = company or frappe.db.get_value("Company", {}, "name")
	for fieldname in ("default_expense_claim_payable_account", "default_payable_account"):
		account = frappe.db.get_value("Company", company, fieldname)
		# Guard against misconfigured defaults (e.g. Cash): GL posting requires Payable
		if account and frappe.db.get_value("Account", account, "account_type") == "Payable":
			return account

	account = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Payable", "is_group": 0, "disabled": 0},
		"name",
	)
	if account:
		return account

	frappe.throw(f"No payable account found for company {company}")


def get_or_create_expense_account(company=None):
	company = company or frappe.db.get_value("Company", {}, "name")
	account = frappe.db.get_value(
		"Account",
		{"company": company, "root_type": "Expense", "is_group": 0, "disabled": 0},
		"name",
	)
	if account:
		return account

	account = frappe.db.get_value(
		"Account",
		{"company": company, "is_group": 0, "disabled": 0},
		"name",
	)
	if account:
		return account

	frappe.throw(f"No expense account found for company {company}")


def get_or_create_expense_claim_type():
	name = "_Test Accounting Expense"
	company = frappe.db.get_value("Company", {}, "name")
	expense_account = get_or_create_expense_account(company)

	if frappe.db.exists("Expense Claim Type", name):
		claim_type = frappe.get_doc("Expense Claim Type", name)
		if not any(row.company == company and row.default_account for row in claim_type.accounts):
			claim_type.append("accounts", {"company": company, "default_account": expense_account})
			claim_type.save(ignore_permissions=True)
		return name

	frappe.get_doc(
		{
			"doctype": "Expense Claim Type",
			"expense_type": name,
			"accounts": [{"company": company, "default_account": expense_account}],
		}
	).insert(ignore_permissions=True)
	return name


def attach_test_receipt(doc):
	frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"receipt-{doc.name}.pdf",
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"content": "test receipt",
			"is_private": 1,
		}
	).insert(ignore_permissions=True)


def make_expense_claim(
	employee,
	project,
	amount=1500,
	owner=None,
	vendor_override_reason=None,
	budget_override_reason=None,
	ensure_project_account=True,
):
	expense_type = get_or_create_expense_claim_type()
	company = frappe.db.get_value("Employee", employee, "company")
	expense_account = None
	if project:
		expense_account = frappe.db.get_value(
			"Project Account Budget",
			{
				"parent": project,
				"parenttype": "Project",
				"parentfield": "account_budgets",
				"is_active": 1,
			},
			"expense_account",
			order_by="idx asc",
		)
	if not expense_account:
		expense_account = get_or_create_expense_account(company)
		if project and ensure_project_account:
			allow_project_expense_account(project, expense_account)
	payable_account = get_or_create_payable_account(company)
	cost_center = frappe.db.get_value("Project", project, "cost_center") if project else None
	department = frappe.db.get_value("Employee", employee, "department")
	claim = frappe.get_doc(
		{
			"doctype": "Expense Claim",
			"employee": employee,
			"company": company,
			"project": project,
			"department": department,
			"payable_account": payable_account,
			"cost_center": cost_center,
			"exchange_rate": 1,
			"expenses": [
				{
					"expense_type": expense_type,
					"project_expense_account": frappe.db.get_value(
						"Project Account Budget",
						{"parent": project, "expense_account": expense_account},
						"budget_key",
					),
					"description": "Test expense",
					"amount": amount,
					"sanctioned_amount": amount,
					"cost_center": cost_center,
					"exchange_rate": 1,
				}
			],
		}
	)
	if owner:
		claim.owner = owner
	if vendor_override_reason:
		claim.vendor_override_reason = vendor_override_reason
	if budget_override_reason:
		claim.budget_override_reason = budget_override_reason
	claim.insert(ignore_permissions=True)
	attach_test_receipt(claim)
	return claim


def allow_project_expense_account(project, account, label=None, approved_amount=0, active=1):
	"""Ensure a test Project exposes one account through the employee-safe selector."""
	if not project or not account:
		return
	project_doc = frappe.get_doc("Project", project)
	for row in project_doc.get("account_budgets") or []:
		if row.expense_account == account:
			if label:
				row.employee_label = label
			row.is_active = active
			save_test_project(project_doc)
			return
	project_doc.append(
		"account_budgets",
		{
			"employee_label": label or frappe.db.get_value("Account", account, "account_name") or account,
			"expense_account": account,
			"approved_amount": approved_amount,
			"is_active": active,
		},
	)
	save_test_project(project_doc)


def get_or_create_supplier():
	supplier_name = "_Test Accounting Supplier"
	existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
	if existing:
		return existing

	supplier_group = frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups"
	return (
		frappe.get_doc(
			{
				"doctype": "Supplier",
				"supplier_name": supplier_name,
				"supplier_group": supplier_group,
				"supplier_type": "Company",
			}
		)
		.insert(ignore_permissions=True)
		.name
	)


def get_or_create_purchase_item():
	item_code = "_Test Accounting Item"
	if frappe.db.exists("Item", item_code):
		return item_code

	item_group = frappe.db.get_value("Item Group", {"is_group": 0}, "name") or "All Item Groups"
	frappe.get_doc(
		{
			"doctype": "Item",
			"item_code": item_code,
			"item_name": item_code,
			"item_group": item_group,
			"stock_uom": "Nos",
			"is_stock_item": 1,
			"is_purchase_item": 1,
		}
	).insert(ignore_permissions=True)
	return item_code


def make_purchase_order(project, amount=1500, owner=None):
	company = frappe.db.get_value("Company", {}, "name")
	supplier = get_or_create_supplier()
	item_code = get_or_create_purchase_item()
	cost_center = frappe.db.get_value("Project", project, "cost_center")
	po = frappe.get_doc(
		{
			"doctype": "Purchase Order",
			"company": company,
			"supplier": supplier,
			"project": project,
			"cost_center": cost_center,
			"transaction_date": nowdate(),
			"schedule_date": nowdate(),
			"currency": frappe.db.get_value("Company", company, "default_currency"),
			"conversion_rate": 1,
			"items": [
				{
					"item_code": item_code,
					"qty": 1,
					"rate": amount,
					"schedule_date": nowdate(),
				}
			],
		}
	)
	if owner:
		po.owner = owner
	po.insert(ignore_permissions=True)
	return po


def get_or_create_bank_account(company=None):
	company = company or frappe.db.get_value("Company", {}, "name")
	for fieldname in ("default_bank_account", "default_cash_account"):
		account = frappe.db.get_value("Company", company, fieldname)
		if account and not frappe.db.get_value("Account", account, "is_group"):
			return account
	account = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Bank", "is_group": 0, "disabled": 0},
		"name",
	)
	if account:
		return account
	account = frappe.db.get_value(
		"Account",
		{"company": company, "account_type": "Cash", "is_group": 0, "disabled": 0},
		"name",
	)
	if account:
		return account
	frappe.throw(f"No bank/cash account found for company {company}")


def make_purchase_invoice(project, amount=1500, purchase_order=None):
	"""Insert a draft Purchase Invoice. Link `purchase_order` on the item when given."""
	company = frappe.db.get_value("Company", {}, "name")
	supplier = get_or_create_supplier()
	item_code = get_or_create_purchase_item()
	cost_center = frappe.db.get_value("Project", project, "cost_center") if project else None
	expense_account = get_or_create_expense_account(company)
	credit_to = get_or_create_payable_account(company)
	item_row = {
		"item_code": item_code,
		"qty": 1,
		"rate": amount,
		"expense_account": expense_account,
		"cost_center": cost_center,
		"project": project,
	}
	if purchase_order:
		item_row["purchase_order"] = purchase_order
		po_item = frappe.db.get_value("Purchase Order Item", {"parent": purchase_order}, "name")
		if po_item:
			item_row["po_detail"] = po_item
	pi = frappe.get_doc(
		{
			"doctype": "Purchase Invoice",
			"company": company,
			"supplier": supplier,
			"project": project,
			"cost_center": cost_center,
			"posting_date": nowdate(),
			"due_date": nowdate(),
			"credit_to": credit_to,
			"update_stock": 0,
			"items": [item_row],
		}
	)
	pi.insert(ignore_permissions=True)
	return pi


def make_purchase_invoice_from_po(po_name):
	from erpnext.buying.doctype.purchase_order.purchase_order import make_purchase_invoice as map_pi

	po = frappe.get_doc("Purchase Order", po_name)
	if po.docstatus != 1:
		frappe.throw("Purchase Invoice requires a submitted Purchase Order.")

	pi = map_pi(po_name)
	pi.flags.ignore_permissions = True
	if not pi.get("credit_to"):
		pi.credit_to = get_or_create_payable_account(pi.company)
	pi.insert(ignore_permissions=True)
	return pi


def make_supplier_payment_entry(reference_doctype, reference_name):
	from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

	pe = get_payment_entry(reference_doctype, reference_name)
	pe.flags.ignore_permissions = True
	if not pe.get("paid_from"):
		pe.paid_from = get_or_create_bank_account(pe.company)
	pe.insert(ignore_permissions=True)
	return pe


def set_project_budget(
	project,
	allocated_amount,
	project_control="Warn Only",
	account_control="No Control",
	account_budgets=None,
):
	project_doc = frappe.get_doc("Project", project)
	project_doc.project_budget_control = project_control
	project_doc.total_approved_budget = allocated_amount
	project_doc.account_budget_control = account_control
	existing = {row.expense_account: row for row in project_doc.get("account_budgets") or []}
	if account_budgets is None:
		save_test_project(project_doc)
		return project_doc
	for row in project_doc.account_budgets:
		row.is_active = 0
	for account, amount in account_budgets or []:
		if account in existing:
			existing[account].approved_amount = amount
			existing[account].is_active = 1
		else:
			project_doc.append(
				"account_budgets",
				{
					"employee_label": frappe.db.get_value("Account", account, "account_name") or account,
					"expense_account": account,
					"approved_amount": amount,
					"is_active": 1,
				},
			)
	save_test_project(project_doc)
	return project_doc


def save_test_project(project_doc):
	"""Persist fixture-only setup through the non-client approval context.

	Production code cannot set this ContextVar; tests use it only to prepare
	legacy accounting fixtures without manufacturing an approval request.
	"""
	from volunteering.volunteering.project_account_mapping import mapping_context
	from volunteering.volunteering.project_proposals import _application

	previous_user = frappe.session.user
	frappe.set_user("Administrator")
	project_doc.project_budget_revision_reason = "Automated test fixture setup"
	token = _application.set((None if project_doc.is_new() else project_doc.name, "test-fixture"))
	try:
		with mapping_context(project_doc.name):
			project_doc.save(ignore_permissions=True)
	finally:
		_application.reset(token)
		frappe.set_user(previous_user)
	return project_doc


def set_project_department_budget(project, department, allocated_amount):
	"""Compatibility helper: department is retained but no longer enforced."""
	project_doc = set_project_budget(project, allocated_amount)
	project_doc.department_budgets = []
	project_doc.append(
		"department_budgets",
		{"department": department, "allocated_amount": allocated_amount},
	)
	save_test_project(project_doc)
	return project_doc
