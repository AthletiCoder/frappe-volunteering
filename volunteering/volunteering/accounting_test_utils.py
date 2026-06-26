import frappe
from frappe.utils import add_days, nowdate


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
		if department_head and frappe.db.get_value("Department", existing, "department_head") != department_head:
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
	return frappe.get_doc(
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
	).insert(ignore_permissions=True).name


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
	return frappe.get_doc(
		{
			"doctype": "Project",
			"project_name": project_name,
			"company": company,
			"cost_center": cost_center,
		}
	).insert(ignore_permissions=True).name


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

	existing_leaf = frappe.db.get_value(
		"Cost Center", {"company": company, "is_group": 0}, "name"
	)
	if existing_leaf:
		return existing_leaf

	parent_cost_center = _get_parent_cost_center(company)
	if not parent_cost_center:
		frappe.throw(f"No parent Cost Center found for company {company}")

	return frappe.get_doc(
		{
			"doctype": "Cost Center",
			"cost_center_name": "_Test Accounting",
			"company": company,
			"parent_cost_center": parent_cost_center,
		}
	).insert(ignore_permissions=True).name


def get_or_create_payable_account(company=None):
	company = company or frappe.db.get_value("Company", {}, "name")
	for fieldname in ("default_expense_claim_payable_account", "default_payable_account"):
		account = frappe.db.get_value("Company", company, fieldname)
		if account:
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
			claim_type.append(
				"accounts", {"company": company, "default_account": expense_account}
			)
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
			"file_name": f"receipt-{doc.name}.txt",
			"attached_to_doctype": doc.doctype,
			"attached_to_name": doc.name,
			"content": "test receipt",
			"is_private": 1,
		}
	).insert(ignore_permissions=True)


def make_expense_claim(employee, project, amount=1500, owner=None):
	expense_type = get_or_create_expense_claim_type()
	company = frappe.db.get_value("Employee", employee, "company")
	payable_account = get_or_create_payable_account(company)
	cost_center = frappe.db.get_value("Project", project, "cost_center")
	claim = frappe.get_doc(
		{
			"doctype": "Expense Claim",
			"employee": employee,
			"company": company,
			"project": project,
			"payable_account": payable_account,
			"cost_center": cost_center,
			"exchange_rate": 1,
			"expenses": [
				{
					"expense_type": expense_type,
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
	claim.insert(ignore_permissions=True)
	attach_test_receipt(claim)
	return claim


def get_or_create_supplier():
	supplier_name = "_Test Accounting Supplier"
	existing = frappe.db.get_value("Supplier", {"supplier_name": supplier_name}, "name")
	if existing:
		return existing

	supplier_group = frappe.db.get_value("Supplier Group", {}, "name") or "All Supplier Groups"
	return frappe.get_doc(
		{
			"doctype": "Supplier",
			"supplier_name": supplier_name,
			"supplier_group": supplier_group,
			"supplier_type": "Company",
		}
	).insert(ignore_permissions=True).name


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


def set_project_department_budget(project, department, allocated_amount):
	project_doc = frappe.get_doc("Project", project)
	project_doc.department_budgets = []
	project_doc.append(
		"department_budgets",
		{"department": department, "allocated_amount": allocated_amount},
	)
	project_doc.save(ignore_permissions=True)
	return project_doc
