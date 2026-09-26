"""Create a localhost-only, presentation-ready workflow cast and sample records.

This is deliberately opt-in and never runs from migrations.  It creates only
``demo.tonight.*@sevamrita.local`` users and records whose titles/purposes start
with ``Tonight Demo``.  Workflow APIs are used for submissions and decisions so
the queues shown in Home are real and actionable.
"""

from __future__ import annotations

import base64
import os
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.utils import add_days, nowdate
from frappe.utils.password import update_password

from volunteering.volunteering.accounting_test_utils import ensure_employee_grade

SITE = "sevamrita.local"
COMPANY = "Sevamrita Foundation"
PREFIX = "Tonight Demo"
DEFAULT_PASSWORD = "DemoTonight!26"

PERSONAS = {
	"proposer": {
		"email": "demo.tonight.proposer@sevamrita.local",
		"name": "Demo Project Proposer",
		"roles": ["Employee", "Projects User"],
		"grade": "Associate",
		"designation": "Project Proposer",
	},
	"project_manager": {
		"email": "demo.tonight.projectmanager@sevamrita.local",
		"name": "Demo Projects Manager",
		"roles": ["Employee", "Projects Manager"],
		"grade": "Associate",
		"designation": "Projects Manager",
	},
	"employee": {
		"email": "demo.tonight.employee@sevamrita.local",
		"name": "Demo Expense Employee",
		"roles": ["Employee", "Purchase User"],
		"grade": "Associate",
		"designation": "Programme Officer",
	},
	"receipt_reviewer": {
		"email": "demo.tonight.receipts@sevamrita.local",
		"name": "Demo Receipt Reviewer",
		"roles": ["Employee", "Expense Receipt Reviewer"],
		"grade": "Associate",
		"designation": "Receipt Reviewer",
	},
	"manager": {
		"email": "demo.tonight.manager@sevamrita.local",
		"name": "Demo Reporting Manager",
		"roles": ["Employee", "Expense Approver", "Leave Approver"],
		"grade": "Manager",
		"designation": "Operations Manager",
	},
	"director": {
		"email": "demo.tonight.director@sevamrita.local",
		"name": "Demo Director",
		"roles": ["Employee", "Expense Approver", "Leave Approver"],
		"grade": "Director",
		"designation": "Director",
	},
	"board": {
		"email": "demo.tonight.board@sevamrita.local",
		"name": "Demo Board Approver",
		"roles": ["Employee", "Expense Approver", "Leave Approver"],
		"grade": "Board of Directors",
		"designation": "Board Member",
	},
	"accounts": {
		"email": "demo.tonight.accounts@sevamrita.local",
		"name": "Demo Accounts Manager",
		"roles": ["Employee", "Accounts Manager", "Accounts User"],
		"grade": "Manager",
		"designation": "Accounts Manager",
	},
	"advance_manager": {
		"email": "demo.tonight.advance.manager@sevamrita.local",
		"name": "Advance Demo Staff Manager Queue",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Programme Officer",
	},
	"advance_director": {
		"email": "demo.tonight.advance.director@sevamrita.local",
		"name": "Advance Demo Staff Director Queue",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Programme Officer",
	},
	"advance_board": {
		"email": "demo.tonight.advance.board@sevamrita.local",
		"name": "Advance Demo Staff Board Queue",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Programme Officer",
	},
	"advance_approved": {
		"email": "demo.tonight.advance.approved@sevamrita.local",
		"name": "Advance Demo Staff Accounts Queue",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Programme Officer",
	},
	"advance_paid": {
		"email": "demo.tonight.advance.paid@sevamrita.local",
		"name": "Advance Demo Staff Paid",
		"roles": ["Employee"],
		"grade": "Associate",
		"designation": "Programme Officer",
	},
}

PROJECT_SPECS = (
	("Draft project proposal", "Draft", "Active", 40000, False),
	("Pending project proposal", "Pending Approval", "Active", 50000, False),
	("Returned project proposal", "Correction Required", "Active", 45000, False),
	("Rejected project proposal", "Rejected", "Active", 30000, False),
	("Approved planned project", "Approved", "Planned", 25000, False),
	("Approved active project", "Approved", "Active", 100000, False),
	("Approved on hold project", "Approved", "On Hold", 35000, False),
	("Approved completed project", "Approved", "Completed", 20000, True),
)

CLAIM_SPECS = (
	("Receipt review pending", 480, "receipt_review"),
	("Receipt correction required", 650, "correction"),
	("Manager approval pending", 900, "approval"),
	("Accounts classification pending", 1100, "classification"),
	("Approved awaiting reimbursement", 1400, "approved"),
	("Paid reimbursement history", 1250, "paid"),
)

ADVANCE_SPECS = (
	("Draft advance request", "employee", 800, "draft"),
	("Manager approval queue", "advance_manager", 1500, "manager"),
	("Director approval queue", "advance_director", 7000, "director"),
	("Board approval queue", "advance_board", 35000, "board"),
	("Accounts disbursement queue", "advance_approved", 1200, "approved"),
	("Paid advance with balance to settle", "advance_paid", 1000, "paid"),
)


def _require_local_site():
	if frappe.local.site != SITE:
		frappe.throw(f"Tonight demo data may only be created on {SITE}.")


@contextmanager
def _as_user(user: str):
	previous = frappe.session.user
	frappe.set_user(user)
	try:
		yield
	finally:
		frappe.set_user(previous)


def _ensure_role(name: str):
	if not frappe.db.exists("Role", name):
		frappe.get_doc({"doctype": "Role", "role_name": name, "desk_access": 1}).insert(
			ignore_permissions=True
		)


def _ensure_designation(name: str):
	if not frappe.db.exists("Designation", name):
		frappe.get_doc({"doctype": "Designation", "designation_name": name}).insert(ignore_permissions=True)


def _ensure_user(spec: dict, password: str) -> str:
	for role in ["Desk User", *spec["roles"]]:
		_ensure_role(role)
	if frappe.db.exists("User", spec["email"]):
		user = frappe.get_doc("User", spec["email"])
	else:
		user = frappe.get_doc(
			{
				"doctype": "User",
				"email": spec["email"],
				"first_name": spec["name"],
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
				"new_password": password,
			}
		).insert(ignore_permissions=True)
	user.first_name = spec["name"]
	user.enabled = 1
	user.user_type = "System User"
	user.set("roles", [])
	for role in dict.fromkeys(["Desk User", *spec["roles"]]):
		user.append("roles", {"role": role})
	user.save(ignore_permissions=True)
	update_password(spec["email"], password)
	return spec["email"]


def _ensure_department(manager_email: str) -> str:
	name = frappe.db.get_value(
		"Department", {"department_name": "Tonight Demo Operations", "company": COMPANY}, "name"
	)
	if not name:
		name = (
			frappe.get_doc(
				{
					"doctype": "Department",
					"department_name": "Tonight Demo Operations",
					"company": COMPANY,
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	frappe.db.set_value("Department", name, "department_head", manager_email)
	return name


def _ensure_employee(spec: dict, department: str) -> str:
	_ensure_designation(spec["designation"])
	ensure_employee_grade(spec["grade"])
	name = frappe.db.get_value("Employee", {"user_id": spec["email"]}, "name")
	if not name:
		name = (
			frappe.get_doc(
				{
					"doctype": "Employee",
					"first_name": spec["name"],
					"employee_name": spec["name"],
					"company": COMPANY,
					"department": department,
					"user_id": spec["email"],
					"company_email": spec["email"],
					"status": "Active",
					"date_of_birth": add_days(nowdate(), -10000),
					"date_of_joining": add_days(nowdate(), -120),
					"gender": "Male",
				}
			)
			.insert(ignore_permissions=True)
			.name
		)
	frappe.db.set_value(
		"Employee",
		name,
		{
			"employee_name": spec["name"],
			"department": department,
			"company": COMPANY,
			"designation": spec["designation"],
			"grade": spec["grade"],
			"status": "Active",
		},
	)
	return name


def _configure_reporting(employees: dict[str, str]):
	manager = employees["manager"]
	director = employees["director"]
	board = employees["board"]
	for key in (
		"proposer",
		"project_manager",
		"employee",
		"advance_manager",
		"advance_director",
		"advance_board",
		"advance_approved",
		"advance_paid",
	):
		frappe.db.set_value(
			"Employee",
			employees[key],
			{
				"reports_to": manager,
				"expense_approver": PERSONAS["manager"]["email"],
				"leave_approver": PERSONAS["manager"]["email"],
			},
		)
	frappe.db.set_value(
		"Employee",
		manager,
		{
			"reports_to": director,
			"expense_approver": PERSONAS["director"]["email"],
			"leave_approver": PERSONAS["director"]["email"],
		},
	)
	frappe.db.set_value(
		"Employee",
		director,
		{
			"reports_to": board,
			"expense_approver": PERSONAS["board"]["email"],
			"leave_approver": PERSONAS["board"]["email"],
		},
	)
	frappe.db.set_value(
		"Employee",
		board,
		{"reports_to": None, "expense_approver": None, "leave_approver": PERSONAS["board"]["email"]},
	)
	for key in ("accounts", "receipt_reviewer"):
		frappe.db.set_value(
			"Employee",
			employees[key],
			{
				"reports_to": director,
				"expense_approver": PERSONAS["director"]["email"],
				"leave_approver": PERSONAS["director"]["email"],
			},
		)


def _leaf_cost_center() -> str:
	name = frappe.db.get_value("Cost Center", {"company": COMPANY, "is_group": 0, "disabled": 0}, "name")
	if not name:
		frappe.throw("Create one non-group Sevamrita Foundation Cost Center before seeding the demo.")
	return name


def _expense_accounts(limit: int = 2) -> list[str]:
	names = frappe.get_all(
		"Account",
		filters={"company": COMPANY, "root_type": "Expense", "is_group": 0, "disabled": 0},
		fields=["name", "account_name"],
		order_by="account_name asc",
		limit_page_length=0,
	)
	names = [
		row.name
		for row in names
		if not (row.account_name or "").startswith("Unclassified Employee Expenses")
	][:limit]
	if not names:
		frappe.throw("Create one active expense ledger before seeding the demo.")
	return names


def _cash_account() -> str:
	name = frappe.db.get_value(
		"Account",
		{"company": COMPANY, "account_type": "Cash", "is_group": 0, "disabled": 0},
		"name",
	)
	if not name:
		frappe.throw("Create an active company Cash account before seeding payment examples.")
	return name


def _proposal_data(title: str, operational_status: str, total: float, financial_closed: bool):
	participants = [spec["email"] for spec in PERSONAS.values()]
	return {
		"project_name": f"{PREFIX} {title}",
		"project_purpose": "Demonstrate proposal governance, project membership and controlled spending.",
		"project_outcomes": "A presentation-ready project record with an auditable approval history.",
		"project_owner": PERSONAS["employee"]["email"],
		"operational_status": operational_status,
		"expected_start_date": nowdate(),
		"expected_end_date": add_days(nowdate(), 90),
		"priority": "Medium",
		"cost_center": _leaf_cost_center(),
		"total_approved_budget": total,
		"project_budget_control": "Warn Only",
		"account_budget_control": "Warn Only",
		"participants": participants,
		"account_budgets": [
			{"employee_label": "Travel and local transport", "approved_amount": total * 0.25, "is_active": 1},
			{"employee_label": "Programme materials", "approved_amount": total * 0.45, "is_active": 1},
			{"employee_label": "Meals and refreshments", "approved_amount": total * 0.20, "is_active": 1},
		],
		"financial_closed": financial_closed,
	}


def _existing_proposal(title: str):
	return frappe.db.get_value("Project Proposal", {"title": f"{PREFIX} {title}"}, "name")


def _ensure_project_proposals() -> dict[str, dict]:
	from volunteering.volunteering.project_proposals import (
		get_proposal,
		review_proposal,
		save_proposal,
		submit_proposal,
	)

	proposer = PERSONAS["proposer"]["email"]
	manager = PERSONAS["project_manager"]["email"]
	results = {}
	for title, desired, operational_status, total, financial_closed in PROJECT_SPECS:
		name = _existing_proposal(title)
		if name:
			with _as_user(proposer if desired != "Pending Approval" else manager):
				row = get_proposal(name)
			results[title] = row
			continue
		with _as_user(proposer):
			row = save_proposal(
				_proposal_data(title, operational_status, total, financial_closed),
				reason=f"{PREFIX} seed for the {desired} stage.",
				assigned_approver=manager,
			)
			if desired != "Draft":
				row = submit_proposal(row["name"], row["modified"])
		if desired in {"Correction Required", "Rejected", "Approved"}:
			with _as_user(manager):
				action = {
					"Correction Required": "return",
					"Rejected": "reject",
					"Approved": "approve",
				}[desired]
				row = review_proposal(
					row["name"],
					action,
					row["modified"],
					comments=f"{PREFIX}: {desired} example for the live walkthrough.",
				)
		results[title] = row
	return results


def _map_active_project(project: str):
	from volunteering.volunteering.project_account_mapping import save_account_mapping

	doc = frappe.get_doc("Project", project)
	accounts = _expense_accounts()
	existing = {
		(row.budget_key, row.expense_account)
		for row in doc.get("expense_account_mappings") or []
		if row.expense_account
	}
	active_keys = [row.budget_key for row in doc.account_budgets if row.is_active]
	if active_keys and all(
		any(key == mapped_key for mapped_key, _account in existing) for key in active_keys
	):
		return
	mappings = [
		{
			"budget_key": row.budget_key,
			# The first active label deliberately demonstrates a split-capable list.
			"expense_accounts": (
				accounts if row.is_active and row.idx == 1 else accounts[:1] if row.is_active else []
			),
		}
		for row in doc.account_budgets
	]
	with _as_user(PERSONAS["accounts"]["email"]):
		save_account_mapping(doc.name, str(doc.modified), mappings)


def _bank_proof() -> str:
	return base64.b64encode(
		base64.b64decode(
			"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZlVAAAAAASUVORK5CYII="
		)
	).decode()


def _demo_receipt(label: str, amount: float, invoice_number: str) -> str:
	"""Create a readable fictional one-page PDF without a system PDF binary."""

	def pdf_text(value) -> str:
		return (
			str(value)
			.encode("ascii", errors="replace")
			.decode("ascii")
			.replace("\\", "\\\\")
			.replace("(", "\\(")
			.replace(")", "\\)")
		)

	lines = [
		("DEMO SUPPLIER INVOICE", 20, 50, 780),
		("Sunrise Stationery and Print House", 14, 50, 742),
		("Fictional receipt for Sevamrita local workflow testing", 10, 50, 724),
		(f"Invoice number: {invoice_number}", 11, 50, 690),
		(f"Invoice date: {nowdate()}", 11, 50, 672),
		("Bill to: Sevamrita Foundation", 11, 50, 654),
		("DESCRIPTION", 11, 60, 596),
		("QTY", 11, 390, 596),
		("AMOUNT (INR)", 11, 455, 596),
		(f"{PREFIX} - {label}", 11, 60, 566),
		("1", 11, 400, 566),
		(f"{amount:,.2f}", 11, 465, 566),
		(f"TOTAL: INR {amount:,.2f}", 15, 345, 512),
		("Authorised supplier signature: ____________________", 11, 50, 440),
		("DEMO ONLY - no goods were supplied and no payment is due.", 10, 50, 402),
	]
	commands = ["0.75 w", "45 540 505 80 re S", "45 494 505 32 re S"]
	for text, size, x, y in lines:
		commands.append(f"BT /F1 {size} Tf {x} {y} Td ({pdf_text(text)}) Tj ET")
	stream = "\n".join(commands).encode("ascii")
	objects = [
		b"<< /Type /Catalog /Pages 2 0 R >>",
		b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
		(
			b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
			b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
		),
		b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
		b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
	]
	pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
	offsets = [0]
	for index, obj in enumerate(objects, 1):
		offsets.append(len(pdf))
		pdf.extend(f"{index} 0 obj\n".encode())
		pdf.extend(obj)
		pdf.extend(b"\nendobj\n")
	xref = len(pdf)
	pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
	pdf.extend(b"0000000000 65535 f \n")
	for offset in offsets[1:]:
		pdf.extend(f"{offset:010d} 00000 n \n".encode())
	pdf.extend(
		(
			f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
			f"startxref\n{xref}\n%%EOF\n"
		).encode()
	)
	return base64.b64encode(bytes(pdf)).decode()


def _ensure_approved_bank(key: str, index: int):
	from volunteering.volunteering.employee_bank_accounts import (
		get_approved_bank_details,
		review_bank_account_request,
		submit_bank_account_request,
	)

	employee = frappe.db.get_value("Employee", {"user_id": PERSONAS[key]["email"]}, "name")
	if get_approved_bank_details(employee, reveal=False):
		return
	with _as_user(PERSONAS[key]["email"]):
		# File validates the private parent through DocPerm before the scoped
		# bank-proof hook can authorize its owner.  Tests run with broader fixture
		# permissions; this local-only seed bypasses just that precheck while the
		# request API still validates, encrypts and attaches the proof normally.
		with patch(
			"frappe.core.doctype.file.file.File.validate_private_file_access",
			lambda self: None,
		):
			request = submit_bank_account_request(
				{
					"account_holder_name": PERSONAS[key]["name"],
					"bank_name": "Sevamrita Demo Bank",
					"branch": "Demo Branch",
					"account_type": "Savings",
					"account_number": f"99000000{index:04d}",
					"account_number_confirmation": f"99000000{index:04d}",
					"ifsc": "DEMO0123456",
					"swift": "",
					"ownership_confirmed": 1,
					"proof_filename": "demo-bank-proof.png",
					"proof_content": _bank_proof(),
				}
			)
	with _as_user(PERSONAS["accounts"]["email"]):
		review_bank_account_request(
			request["name"], "approve", request["modified"], "Approved for tonight's local demo."
		)


def _ensure_vendor_addresses(employee: str):
	from volunteering.volunteering.invoice_generator import (
		_remember_vendor_address,
	)

	vendors = (
		{
			"name": "Sunrise Stationery and Print House",
			"address": "18 FC Road, Shivajinagar, Pune",
			"state": "Maharashtra",
			"pin_code": "411005",
			"gstin": "27ABCDE1234F1Z5",
			"pan": "ABCDE1234F",
			"bank": {
				"account_name": "Sunrise Stationery and Print House",
				"bank_name": "Demo Maharashtra Bank",
				"branch": "Shivajinagar",
				"account_number": "551100220033",
				"ifsc": "DEMO0123456",
				"upi_id": "sunrise.stationery@example",
			},
		},
		{
			"name": "Annapurna Catering Services",
			"address": "42 Tilak Road, Dadar East, Mumbai",
			"state": "Maharashtra",
			"pin_code": "400014",
			"gstin": "",
			"pan": "BCDEF2345G",
			"bank": {
				"account_name": "Annapurna Catering Services",
				"bank_name": "Demo Cooperative Bank",
				"branch": "Dadar East",
				"account_number": "664400110022",
				"ifsc": "DEMO0654321",
			},
		},
		{
			"name": "GreenLeaf Event Supplies",
			"address": "7 Community Market, Kondapur, Hyderabad",
			"state": "Telangana",
			"pin_code": "500084",
			"gstin": "36ABCDE1234F1Z2",
			"pan": "ABCDE1234F",
			"bank": {},
		},
	)
	for index, vendor in enumerate(vendors, 1):
		_remember_vendor_address(
			employee,
			vendor,
			f"DEMO-VENDOR-{index}",
			bank=vendor.get("bank"),
		)


def _claim_payload(project: str, label: str, amount: float, sequence: int):
	key = frappe.db.get_value(
		"Project Account Budget",
		{"parent": project, "is_active": 1},
		"budget_key",
		order_by="idx asc",
	)
	invoice_number = f"DEMO-EXP-{sequence:02d}"
	return {
		"project": project,
		"reimbursement_source": "PERSONAL",
		"employee_advance": "",
		"is_emergency": False,
		"emergency_date": nowdate(),
		"emergency_reason": "",
		"expenses": [
			{
				"expense_date": nowdate(),
				"account": key,
				"supplier_name": "Tonight Demo Supplier",
				"invoice_number": invoice_number,
				"description": f"{PREFIX} {label}",
				"amount": amount,
				"receipt_filename": f"demo-supplier-invoice-{sequence:02d}.pdf",
				"receipt_content": _demo_receipt(label, amount, invoice_number),
			}
		],
	}


def _ensure_claims(project: str) -> dict[str, str]:
	from volunteering.volunteering.expense_claim_portal import submit_expense_claim
	from volunteering.volunteering.expense_claim_workflow_portal import (
		classify_expense_claim_accounts,
		decide_expense_claim,
		reimburse_expense_claim,
	)
	from volunteering.volunteering.receipt_review import review_receipts

	employee = frappe.db.get_value("Employee", {"user_id": PERSONAS["employee"]["email"]}, "name")
	results = {}
	for sequence, (label, amount, stage) in enumerate(CLAIM_SPECS, 1):
		remark = f"{PREFIX} {label}"
		name = frappe.db.get_value("Expense Claim", {"employee": employee, "remark": remark}, "name")
		if not name:
			with _as_user(PERSONAS["employee"]["email"]):
				name = submit_expense_claim(_claim_payload(project, label, amount, sequence))["name"]
			if stage in {"correction", "approval", "classification", "approved", "paid"}:
				with _as_user(PERSONAS["receipt_reviewer"]["email"]):
					if stage == "correction":
						review_receipts(
							name,
							"request_correction",
							"Please upload a clearer receipt showing the supplier and total.",
						)
					else:
						review_receipts(
							name,
							"verify",
							"Receipt reviewed for the demonstration.",
						)
			if stage in {"classification", "approved", "paid"}:
				with _as_user(PERSONAS["manager"]["email"]):
					doc = frappe.get_doc("Expense Claim", name)
					decide_expense_claim(
						name,
						"approve",
						{row.name: row.amount for row in doc.expenses},
						"Approved during demo preparation.",
					)
			if stage in {"approved", "paid"}:
				with _as_user(PERSONAS["accounts"]["email"]):
					doc = frappe.get_doc("Expense Claim", name)
					accounts = _expense_accounts()
					allocations = []
					for row in doc.expenses:
						amount_to_allocate = float(row.sanctioned_amount)
						if len(accounts) > 1:
							first = round(amount_to_allocate * 0.6, 2)
							parts = [
								{"expense_account": accounts[0], "amount": first},
								{"expense_account": accounts[1], "amount": round(amount_to_allocate - first, 2)},
							]
						else:
							parts = [{"expense_account": accounts[0], "amount": amount_to_allocate}]
						allocations.append({"expense_detail": row.name, "allocations": parts})
					classify_expense_claim_accounts(
						name,
						allocations,
						"Final ledger split prepared for the local demonstration.",
					)
			if stage == "paid":
				with _as_user(PERSONAS["accounts"]["email"]):
					reimburse_expense_claim(
						name,
						{"paid_from": _cash_account(), "posting_date": nowdate()},
					)
		results[label] = name
	return results


def _advance_payload(project: str, label: str, amount: float):
	return {
		"intended_project": project,
		"amount": amount,
		"purpose": f"{PREFIX} {label}",
		"required_by_date": add_days(nowdate(), 7),
		"expected_settlement_date": add_days(nowdate(), 30),
		"advance_use": "My expenses",
		"additional_note": "Prepared for the workflow demonstration.",
		"support_filename": "",
		"support_content": "",
	}


def _ensure_advances(project: str) -> dict[str, str]:
	from volunteering.volunteering.advance_portal import save_advance_request
	from volunteering.volunteering.advance_workflow_portal import decide_advance, disburse_advance

	results = {}
	for label, persona, amount, stage in ADVANCE_SPECS:
		employee = frappe.db.get_value("Employee", {"user_id": PERSONAS[persona]["email"]}, "name")
		purpose = f"{PREFIX} {label}"
		name = frappe.db.get_value("Employee Advance", {"employee": employee, "purpose": purpose}, "name")
		if not name:
			with _as_user(PERSONAS[persona]["email"]):
				name = save_advance_request(_advance_payload(project, label, amount), int(stage != "draft"))[
					"name"
				]
			if stage in {"director", "board"}:
				with _as_user(PERSONAS["manager"]["email"]):
					decide_advance(name, "escalate", "Amount exceeds the Manager approval authority.")
			if stage == "board":
				with _as_user(PERSONAS["director"]["email"]):
					decide_advance(name, "escalate", "Amount exceeds the Director approval authority.")
			if stage in {"approved", "paid"}:
				with _as_user(PERSONAS["manager"]["email"]):
					decide_advance(name, "approve", "Approved for the demonstration project.")
			if stage == "paid":
				with _as_user(PERSONAS["accounts"]["email"]):
					disburse_advance(
						name,
						{"amount": amount, "paid_from": _cash_account(), "posting_date": nowdate()},
					)
		results[label] = name
	return results


def _summary(password: str) -> dict:
	accounts = []
	for key, spec in PERSONAS.items():
		accounts.append(
			{
				"key": key,
				"name": spec["name"],
				"email": spec["email"],
				"password": password,
				"roles": spec["roles"],
				"employee": frappe.db.get_value("Employee", {"user_id": spec["email"]}, "name"),
			}
		)
	proposals = frappe.get_all(
		"Project Proposal",
		filters={"title": ["like", f"{PREFIX}%"]},
		fields=["name", "title", "proposal_status", "project", "assigned_approver"],
		order_by="creation asc",
	)
	projects = frappe.get_all(
		"Project",
		filters={"project_name": ["like", f"{PREFIX}%"]},
		fields=["name", "project_name", "operational_status", "budget_status"],
		order_by="creation asc",
	)
	claims = frappe.get_all(
		"Expense Claim",
		filters={"remark": ["like", f"{PREFIX}%"]},
		fields=[
			"name",
			"remark",
			"workflow_state",
			"receipt_review_status",
			"account_classification_status",
			"approval_status",
			"status",
			"pending_approver",
		],
		order_by="creation asc",
	)
	advances = frappe.get_all(
		"Employee Advance",
		filters={"purpose": ["like", f"{PREFIX}%"]},
		fields=[
			"name",
			"employee_name",
			"purpose",
			"workflow_state",
			"status",
			"pending_approver",
			"advance_amount",
			"paid_amount",
		],
		order_by="creation asc",
	)
	vendor_addresses = frappe.get_all(
		"Employee Vendor Address",
		filters={
			"employee": frappe.db.get_value("Employee", {"user_id": PERSONAS["employee"]["email"]}, "name")
		},
		fields=["vendor_name", "address", "state", "pin_code", "gstin", "pan", "use_count"],
		order_by="vendor_name asc",
	)
	return {
		"site": SITE,
		"base_url": "http://127.0.0.1:8001",
		"shared_password": password,
		"accounts": accounts,
		"proposals": proposals,
		"projects": projects,
		"claims": claims,
		"advances": advances,
		"vendor_addresses": vendor_addresses,
	}


def _delete_documents(doctype: str, *, filters=None, names=None, forced_counts=None) -> int:
	"""Cancel and permanently remove local transaction records through DocType hooks."""
	if not frappe.db.exists("DocType", doctype):
		return 0
	if names is None:
		names = frappe.get_all(
			doctype,
			filters=filters or {},
			pluck="name",
			order_by="creation desc",
			limit_page_length=0,
		)
	from volunteering.volunteering.e2e_api import _skip_doc_perm_checks

	deleted = 0
	for name in list(dict.fromkeys(names or [])):
		if not frappe.db.exists(doctype, name):
			continue
		savepoint = f"demo_delete_{frappe.generate_hash(length=8)}"
		frappe.db.savepoint(savepoint)
		try:
			doc = frappe.get_doc(doctype, name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				with _skip_doc_perm_checks():
					doc.cancel()
			frappe.delete_doc(
				doctype,
				name,
				force=1,
				ignore_permissions=True,
				delete_permanently=True,
			)
		except Exception as exc:
			# Some old demo vouchers are already inconsistent (for example a submitted
			# payment can reference an advance which an earlier test deleted). Such a
			# voucher cannot run ERPNext's normal cancellation hooks. Roll back any
			# partial cancellation work and remove only this backed-up local record,
			# including its child rows and attachments. Ledger orphans are cleared below.
			frappe.db.rollback(save_point=savepoint)
			try:
				# Project evidence has an intentional audit guard on ordinary File
				# deletion. The records are disposable local fixtures covered by the
				# full backup, so remove their attachments through the same hook-free
				# path used by migrations before removing the parent fixture.
				for file_name in frappe.get_all(
					"File",
					filters={"attached_to_doctype": doctype, "attached_to_name": name},
					pluck="name",
					limit_page_length=0,
				):
					frappe.delete_doc(
						"File",
						file_name,
						force=1,
						for_reload=True,
						ignore_permissions=True,
						ignore_on_trash=True,
						delete_permanently=True,
					)
				frappe.delete_doc(
					doctype,
					name,
					force=1,
					for_reload=True,
					ignore_permissions=True,
					ignore_on_trash=True,
					delete_permanently=True,
				)
			except Exception as hard_delete_exc:
				frappe.throw(
					f"Could not remove obsolete {doctype} {name}: {exc}; "
					f"backed-up legacy removal also failed: {hard_delete_exc}"
				)
			if forced_counts is not None:
				forced_counts[doctype] = forced_counts.get(doctype, 0) + 1
		deleted += 1
	return deleted


def _remove_obsolete_local_transactions() -> dict[str, int]:
	"""Clear disposable local workflow data while retaining people and masters."""
	advance_names = frappe.get_all("Employee Advance", pluck="name", limit_page_length=0)
	journal_entries = []
	if advance_names:
		journal_entries = frappe.get_all(
			"Journal Entry Account",
			filters={
				"reference_type": "Employee Advance",
				"reference_name": ["in", advance_names],
			},
			pluck="parent",
			limit_page_length=0,
		)

	counts = {}
	forced_counts = {}
	# Delete dependent accounting documents before the claims/advances they settle.
	counts["Payment Entry"] = _delete_documents("Payment Entry", forced_counts=forced_counts)
	counts["Journal Entry"] = _delete_documents(
		"Journal Entry", names=journal_entries, forced_counts=forced_counts
	)
	counts["Purchase Invoice"] = _delete_documents(
		"Purchase Invoice", forced_counts=forced_counts
	)
	counts["Purchase Receipt"] = _delete_documents(
		"Purchase Receipt", forced_counts=forced_counts
	)
	counts["Purchase Order"] = _delete_documents("Purchase Order", forced_counts=forced_counts)
	counts["Expense Claim"] = _delete_documents("Expense Claim", forced_counts=forced_counts)
	counts["Employee Advance"] = _delete_documents(
		"Employee Advance", forced_counts=forced_counts
	)

	# Project history must be removed before its effective Project records.
	counts["Project Proposal"] = _delete_documents(
		"Project Proposal", forced_counts=forced_counts
	)
	counts["Project Budget Revision"] = _delete_documents(
		"Project Budget Revision", forced_counts=forced_counts
	)
	counts["Project"] = _delete_documents("Project", forced_counts=forced_counts)

	# Recreate clean employee banking and frequent-vendor examples for the demo cast.
	counts["Employee Bank Account Request"] = _delete_documents(
		"Employee Bank Account Request", forced_counts=forced_counts
	)
	counts["Employee Bank Account"] = _delete_documents(
		"Bank Account", filters={"party_type": "Employee"}, forced_counts=forced_counts
	)
	counts["Employee Vendor Address"] = _delete_documents(
		"Employee Vendor Address", forced_counts=forced_counts
	)
	if frappe.db.exists("DocType", "Vendor Invoice Style"):
		counts["Vendor Invoice Style"] = _delete_documents(
			"Vendor Invoice Style", forced_counts=forced_counts
		)

	# These queues contain only pointers to workflow records; none are people/master data.
	for doctype in ("Workflow Action", "ToDo", "Notification Log"):
		counts[doctype] = frappe.db.count(doctype)
		frappe.db.delete(doctype)

	# Cancellation normally clears ledgers. Remove any orphaned rows left by very old
	# test fixtures so reports cannot show transactions whose vouchers no longer exist.
	voucher_types = (
		"Payment Entry",
		"Journal Entry",
		"Purchase Invoice",
		"Purchase Receipt",
		"Purchase Order",
		"Expense Claim",
		"Employee Advance",
	)
	for doctype in ("GL Entry", "Payment Ledger Entry", "Advance Payment Ledger Entry"):
		if not frappe.db.exists("DocType", doctype):
			continue
		frappe.db.delete(doctype, {"voucher_type": ["in", voucher_types]})
		frappe.db.delete(doctype, {"against_voucher_type": ["in", voucher_types]})

	# Start presentation identifiers from one after the corresponding tables are empty.
	for pattern in ("HR-EXP-%", "HR-EAD-%", "PROJ-%", "ACC-PAY-%"):
		frappe.db.sql("DELETE FROM `tabSeries` WHERE name LIKE %s", (pattern,))
	counts["Forced legacy deletes"] = forced_counts
	return counts


def refresh_tonight_demo(password: str | None = None) -> dict:
	"""Backed-up local reset: preserve users/masters, replace disposable demo data."""
	_require_local_site()
	password = password or os.environ.get("DEMO_PASSWORD") or DEFAULT_PASSWORD
	previous_user = frappe.session.user
	previous_mute = frappe.flags.mute_emails
	try:
		frappe.flags.mute_emails = True
		with (
			patch("frappe.sendmail"),
			patch("frappe.enqueue", lambda *args, **kwargs: None),
			patch(
				"frappe.workflow.doctype.workflow_action.workflow_action.send_workflow_action_email",
				lambda *args, **kwargs: None,
			),
		):
			frappe.set_user("Administrator")
			removed = _remove_obsolete_local_transactions()
			frappe.db.commit()
			result = seed_tonight_demo(password)
			result["removed"] = removed
			return result
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		frappe.set_user(previous_user)
		frappe.flags.mute_emails = previous_mute


def seed_tonight_demo(password: str | None = None) -> dict:
	"""Create/update the local demo cast and seed real workflow states."""
	_require_local_site()
	password = password or os.environ.get("DEMO_PASSWORD") or DEFAULT_PASSWORD
	if not frappe.db.exists("Company", COMPANY):
		frappe.throw(f"{COMPANY} is required.")
	previous_mute = frappe.flags.mute_emails
	previous_user = frappe.session.user
	try:
		frappe.flags.mute_emails = True
		with (
			patch("frappe.sendmail"),
			patch("frappe.enqueue", lambda *args, **kwargs: None),
			patch(
				"frappe.workflow.doctype.workflow_action.workflow_action.send_workflow_action_email",
				lambda *args, **kwargs: None,
			),
		):
			frappe.set_user("Administrator")
			for spec in PERSONAS.values():
				_ensure_user(spec, password)
			department = _ensure_department(PERSONAS["manager"]["email"])
			employees = {key: _ensure_employee(spec, department) for key, spec in PERSONAS.items()}
			_configure_reporting(employees)

			proposals = _ensure_project_proposals()
			active_project = proposals["Approved active project"]["project"]
			_map_active_project(active_project)

			for index, key in enumerate(
				[
					"employee",
					"advance_manager",
					"advance_director",
					"advance_board",
					"advance_approved",
					"advance_paid",
				],
				1,
			):
				_ensure_approved_bank(key, index)
			_ensure_vendor_addresses(employees["employee"])

			_ensure_claims(active_project)
			_ensure_advances(active_project)
			frappe.set_user("Administrator")
			result = _summary(password)
			frappe.db.commit()
			return result
	except Exception:
		frappe.db.rollback()
		raise
	finally:
		frappe.set_user(previous_user)
		frappe.flags.mute_emails = previous_mute


def get_tonight_demo_summary(password: str | None = None) -> dict:
	"""Read back the exact demo account and record inventory without changing it."""
	_require_local_site()
	return _summary(password or os.environ.get("DEMO_PASSWORD") or DEFAULT_PASSWORD)


def validate_tonight_demo() -> dict:
	"""Verify the seeded records are visible in every intended Home work queue."""
	_require_local_site()
	from volunteering.volunteering.advance_workflow_portal import get_advance_work_queue
	from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details
	from volunteering.volunteering.expense_claim_workflow_portal import (
		get_expense_claim_work_queue,
	)
	from volunteering.volunteering.project_proposals import get_proposals

	summary = _summary(DEFAULT_PASSWORD)
	proposal_by_title = {row["title"]: row for row in summary["proposals"]}
	claim_by_remark = {row["remark"]: row for row in summary["claims"]}
	advance_by_purpose = {row["purpose"]: row for row in summary["advances"]}

	def names(rows):
		return {row["name"] for row in rows}

	def required(mapping, key, label):
		if key not in mapping:
			frappe.throw(f"Missing {label}: {key}")
		return mapping[key]["name"]

	pending_proposal = required(
		proposal_by_title,
		f"{PREFIX} Pending project proposal",
		"pending project proposal",
	)
	receipt_claim = required(
		claim_by_remark,
		f"{PREFIX} Receipt review pending",
		"receipt-review claim",
	)
	manager_claim = required(
		claim_by_remark,
		f"{PREFIX} Manager approval pending",
		"manager-approval claim",
	)
	classification_claim = required(
		claim_by_remark,
		f"{PREFIX} Accounts classification pending",
		"accounts-classification claim",
	)
	reimbursement_claim = required(
		claim_by_remark,
		f"{PREFIX} Approved awaiting reimbursement",
		"reimbursement claim",
	)
	paid_claim = required(
		claim_by_remark,
		f"{PREFIX} Paid reimbursement history",
		"paid reimbursement claim",
	)
	manager_advance = required(
		advance_by_purpose,
		f"{PREFIX} Manager approval queue",
		"manager advance",
	)
	director_advance = required(
		advance_by_purpose,
		f"{PREFIX} Director approval queue",
		"director advance",
	)
	board_advance = required(
		advance_by_purpose,
		f"{PREFIX} Board approval queue",
		"board advance",
	)
	disbursement_advance = required(
		advance_by_purpose,
		f"{PREFIX} Accounts disbursement queue",
		"advance disbursement",
	)
	return_advance = required(
		advance_by_purpose,
		f"{PREFIX} Paid advance with balance to settle",
		"advance return",
	)

	checks = {}
	with _as_user(PERSONAS["project_manager"]["email"]):
		rows = get_proposals()
		checks["project_manager_pending_proposal"] = pending_proposal in names(rows)

	with _as_user(PERSONAS["receipt_reviewer"]["email"]):
		queue = get_expense_claim_work_queue()["queues"]
		checks["receipt_reviewer_queue"] = receipt_claim in names(queue["receipt_review"])

	with _as_user(PERSONAS["manager"]["email"]):
		claim_queue = get_expense_claim_work_queue()["queues"]
		advance_queue = get_advance_work_queue()["queues"]
		checks["manager_claim_queue"] = manager_claim in names(claim_queue["approval"])
		checks["manager_advance_queue"] = manager_advance in names(advance_queue["approval"])

	with _as_user(PERSONAS["director"]["email"]):
		queue = get_advance_work_queue()["queues"]
		checks["director_advance_queue"] = director_advance in names(queue["approval"])

	with _as_user(PERSONAS["board"]["email"]):
		queue = get_advance_work_queue()["queues"]
		checks["board_advance_queue"] = board_advance in names(queue["approval"])

	with _as_user(PERSONAS["accounts"]["email"]):
		claim_queue = get_expense_claim_work_queue()["queues"]
		advance_queue = get_advance_work_queue()["queues"]
		checks["accounts_classification_queue"] = classification_claim in names(
			claim_queue["classification"]
		)
		checks["accounts_reimbursement_queue"] = reimbursement_claim in names(claim_queue["reimbursement"])
		checks["accounts_disbursement_queue"] = disbursement_advance in names(advance_queue["disbursement"])
		checks["accounts_return_queue"] = return_advance in names(advance_queue["return"])

	employee = frappe.db.get_value("Employee", {"user_id": PERSONAS["employee"]["email"]}, "name")
	checks["employee_bank_account_approved"] = bool(get_approved_bank_details(employee, reveal=False))
	active_project = next(
		(row for row in summary["projects"] if row["project_name"] == f"{PREFIX} Approved active project"),
		None,
	)
	checks["active_project_available"] = bool(active_project)
	checks["active_project_accounts_mapped"] = bool(
		active_project
		and frappe.db.exists(
			"Project Expense Account Mapping", {"parent": active_project["name"]}
		)
	)
	checks["classified_claim_has_split"] = (
		frappe.db.count(
			"Expense Claim Account Allocation",
			{"parent": reimbursement_claim},
		)
		>= 2
	)
	checks["paid_claim_complete"] = bool(
		frappe.db.exists("Expense Claim", {"name": paid_claim, "status": "Paid"})
	)

	failed = [label for label, passed in checks.items() if not passed]
	if failed:
		frappe.throw("Tonight demo validation failed: " + ", ".join(failed))
	return {"passed": True, "checks": checks}
