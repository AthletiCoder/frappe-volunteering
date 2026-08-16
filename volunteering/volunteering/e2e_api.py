# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Whitelisted helpers for Playwright E2E (local / developer sites only)."""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe import _
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, cint, flt, getdate, nowdate

from volunteering.volunteering.accounting_test_utils import (
	attach_test_receipt,
	get_or_create_department,
	get_or_create_expense_claim_type,
	get_or_create_payable_account,
	get_or_create_project_with_cost_center,
	get_or_create_supplier,
	make_expense_claim,
	make_purchase_invoice,
	make_purchase_invoice_from_po,
	make_purchase_order,
	make_supplier_payment_entry,
	mute_accounting_test_emails,
	set_project_department_budget,
)
from volunteering.volunteering.attendance_service import process_daily_attendance
from volunteering.volunteering.e2e_seed import PERSONAS, list_e2e_personas, seed_e2e_personas
from volunteering.volunteering.test_utils import (
	ensure_leave_allocation,
	get_or_create_allocatable_leave_type,
)

E2E_PROJECT_NAME = "_E2E Test Project"
PRIVILEGE_LEAVE = "Privilege Leave"
LWP_LEAVE = "Leave Without Pay"


def _guard_e2e():
	site = frappe.local.site or ""
	if not (frappe.conf.developer_mode or site.endswith(".local")):
		frappe.throw(_("E2E API is only available on local / developer sites."), frappe.PermissionError)
	mute_accounting_test_emails()


@contextmanager
def _bypass_leave_access_check():
	"""HRMS get_holidays → validate_leave_access ignores ignore_permissions."""
	with patch(
		"hrms.hr.doctype.leave_application.leave_application.validate_leave_access",
		lambda *args, **kwargs: None,
	):
		yield


def _employee_for_email(email: str) -> str | None:
	return frappe.db.get_value("Employee", {"user_id": email}, "name")


def _cast_employee(alias: str) -> str:
	spec = PERSONAS.get(alias)
	if not spec or spec.get("no_employee"):
		frappe.throw(_(f"Persona {alias} has no Employee"))
	emp = _employee_for_email(spec["email"])
	if not emp:
		frappe.throw(_(f"E2E persona {alias} not seeded — run seed_e2e_personas"))
	return emp


@contextmanager
def _skip_doc_perm_checks():
	from frappe.model.document import Document

	original = Document.check_permission

	def _allow(self, permtype="read", permlevel=None):
		return None

	Document.check_permission = _allow
	try:
		yield
	finally:
		Document.check_permission = original


@contextmanager
def _allow_account_read():
	"""ERPNext get_party_account checks Account DocPerm; E2E staff lack it."""
	import frappe.permissions as perms

	orig_perms = perms.has_permission

	def _has_permission(*args, **kwargs):
		doctype = kwargs.get("doctype")
		doc = kwargs.get("doc")
		if args:
			doctype = doctype or args[0]
		if len(args) > 2:
			doc = doc or args[2]
		if doctype == "Account" or getattr(doc, "doctype", None) == "Account":
			return True
		return orig_perms(*args, **kwargs)

	perms.has_permission = _has_permission
	try:
		yield
	finally:
		perms.has_permission = orig_perms


@contextmanager
def _allow_buying_read():
	"""Map PO → PI / PE checks source-doc read; E2E Accounts may lack Purchase User."""
	import frappe.permissions as perms

	orig_perms = perms.has_permission
	allowed = {"Account", "Purchase Order", "Purchase Invoice", "Payment Entry"}

	def _has_permission(*args, **kwargs):
		doctype = kwargs.get("doctype")
		doc = kwargs.get("doc")
		if args:
			doctype = doctype or args[0]
		if len(args) > 2:
			doc = doc or args[2]
		if doctype in allowed or getattr(doc, "doctype", None) in allowed:
			return True
		return orig_perms(*args, **kwargs)

	perms.has_permission = _has_permission
	try:
		yield
	finally:
		perms.has_permission = orig_perms


def _apply_workflow(doc, action):
	"""Apply a workflow action as the session user.

	Skip Document.check_permission so managers/Accounts can Submit/Approve
	reportee docs. Validate methods (grade limits, spend controls) still run.
	"""
	doc.flags.ignore_permissions = True
	with _skip_doc_perm_checks(), _allow_account_read():
		apply_workflow(doc, action)


def _exc_message(exc: BaseException) -> str:
	msg = str(exc).strip()
	if msg:
		return msg
	if frappe.message_log:
		last = frappe.message_log[-1]
		if isinstance(last, dict):
			return str(last.get("message") or last)
		return str(last)
	return type(exc).__name__


def _strip_rpc_kwargs(kwargs: dict) -> dict:
	"""Frappe RPC injects cmd / _ into **kwargs wrappers."""
	skip = {
		"cmd",
		"method",
		"_",
		"csrf_token",
		"ignore_permissions",
		"ignore_links",
		"ignore_mandatory",
	}
	return {k: v for k, v in kwargs.items() if k not in skip}


@frappe.whitelist()
def get_cast():
	_guard_e2e()
	return list_e2e_personas()


@frappe.whitelist()
def get_fixtures():
	_guard_e2e()
	project = frappe.db.get_value("Project", {"project_name": E2E_PROJECT_NAME}, "name")
	if not project:
		frappe.throw(_("E2E project not found — run ensure_fixtures / globalSetup first."))
	dept = get_or_create_department("E2E Operations")
	return {"project": project, "department": dept}


@frappe.whitelist()
def ensure_fixtures():
	_guard_e2e()
	mute_accounting_test_emails()
	seed_e2e_personas()
	project = frappe.db.get_value("Project", {"project_name": E2E_PROJECT_NAME}, "name")
	if not project:
		project = get_or_create_project_with_cost_center()
		if not frappe.db.exists("Project", {"project_name": E2E_PROJECT_NAME}):
			frappe.db.set_value("Project", project, "project_name", E2E_PROJECT_NAME)
	dept = get_or_create_department("E2E Operations")
	for alias in ("employee", "employee_b", "associate", "manager", "director", "chair"):
		emp = _cast_employee(alias)
		ensure_leave_allocation(emp, get_or_create_allocatable_leave_type(PRIVILEGE_LEAVE))
	ensure_leave_allocation(_cast_employee("employee"), get_or_create_allocatable_leave_type(LWP_LEAVE))
	frappe.db.set_single_value("Daily Work Log Settings", "backdate_limit_days", 14)
	frappe.db.set_single_value("Daily Work Log Settings", "present_hours_threshold", 6)
	try:
		from volunteering.volunteering.doctype.approval_and_advance_limits.approval_and_advance_limits import (
			reset_to_defaults,
		)

		reset_to_defaults()
	except Exception:
		pass
	from volunteering.volunteering.leave_setup import assign_leave_policy_to_employee

	for alias in ("employee", "employee_b", "associate", "manager", "director", "chair"):
		try:
			assign_leave_policy_to_employee(_cast_employee(alias))
		except Exception:
			pass
	unpaid = _cast_employee("unpaid")
	for name in frappe.get_all(
		"Leave Policy Assignment", filters={"employee": unpaid}, pluck="name"
	):
		try:
			doc = frappe.get_doc("Leave Policy Assignment", name)
			if doc.docstatus == 1:
				doc.cancel()
			frappe.delete_doc("Leave Policy Assignment", name, force=1)
		except Exception:
			pass
	frappe.db.commit()
	return {"project": project, "department": dept}


@frappe.whitelist()
def cleanup_day(employee, date):
	_guard_e2e()
	date = getdate(date)
	date_range = {"from_date": ["<=", date], "to_date": [">=", date]}
	for doctype, filters in (
		("Daily Work Log", {"employee": employee, "date": date}),
		("Attendance", {"employee": employee, "attendance_date": date}),
		(
			"Attendance Request",
			{"employee": employee, **date_range},
		),
		(
			"Attendance Regularization Request",
			{"employee": employee, "attendance_date": date},
		),
		(
			"Leave Application",
			{"employee": employee, **date_range},
		),
	):
		for name in frappe.get_all(doctype, filters=filters, pluck="name"):
			try:
				doc = frappe.get_doc(doctype, name)
				if doc.docstatus == 1:
					doc.cancel()
				frappe.delete_doc(doctype, name, force=1)
			except Exception:
				pass
	frappe.db.commit()
	return True


@frappe.whitelist()
def cleanup_leave_span(employee, from_date, to_date):
	"""Cancel overlapping leave in one RPC instead of one HTTP call per day."""
	_guard_e2e()
	from_date, to_date = getdate(from_date), getdate(to_date)
	names = frappe.get_all(
		"Leave Application",
		filters={
			"employee": employee,
			"from_date": ["<=", to_date],
			"to_date": [">=", from_date],
		},
		pluck="name",
	)
	for name in names:
		try:
			doc = frappe.get_doc("Leave Application", name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				doc.cancel()
			frappe.delete_doc("Leave Application", name, force=1)
		except Exception:
			pass
	frappe.db.commit()
	return True


@frappe.whitelist()
def cleanup_employee_advances(employee):
	"""Cancel and delete advances so leftover-unsettled cases start clean."""
	_guard_e2e()
	names = frappe.get_all("Employee Advance", filters={"employee": employee}, pluck="name")
	for name in names:
		try:
			doc = frappe.get_doc("Employee Advance", name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				with _skip_doc_perm_checks():
					doc.cancel()
			frappe.delete_doc("Employee Advance", name, force=1, ignore_permissions=True)
		except Exception:
			pass
	frappe.db.commit()
	return True


@frappe.whitelist()
def cleanup_expense_claims(employee):
	_guard_e2e()
	names = frappe.get_all("Expense Claim", filters={"employee": employee}, pluck="name")
	for name in names:
		try:
			doc = frappe.get_doc("Expense Claim", name)
			if doc.docstatus == 1:
				doc.flags.ignore_permissions = True
				with _skip_doc_perm_checks():
					doc.cancel()
			frappe.delete_doc("Expense Claim", name, force=1, ignore_permissions=True)
		except Exception:
			pass
	frappe.db.commit()
	return True


@frappe.whitelist()
def has_doctype_permission(doctype, ptype="read"):
	_guard_e2e()
	if not frappe.db.exists("DocType", doctype):
		page_name = frappe.db.get_value("Page", {"name": doctype}) or frappe.db.get_value(
			"Page", {"page_name": doctype}
		)
		if not page_name:
			# ERPNext Bank Reconciliation Tool is a workspace/page slug.
			slug = doctype.lower().replace(" ", "-")
			page_name = frappe.db.get_value("Page", slug) or frappe.db.exists("Page", slug)
		if page_name:
			return True
		return bool(frappe.db.exists("DocType", "Bank Transaction")) and bool(
			frappe.has_permission("Bank Transaction", ptype)
		)
	return bool(frappe.has_permission(doctype, ptype))


@frappe.whitelist()
def run_query_report(report_name, filters=None):
	_guard_e2e()
	from frappe.desk.query_report import run

	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or {}
	filters = filters or {}
	if report_name == "General Ledger" and not filters.get("company"):
		filters["company"] = frappe.db.get_value("Company", {}, "name")
		filters.setdefault("from_date", nowdate())
		filters.setdefault("to_date", nowdate())
	result = run(report_name, filters=filters)
	return {
		"columns": result.get("columns") if isinstance(result, dict) else None,
		"ok": True,
		"report": report_name,
	}


@frappe.whitelist()
def get_attendance_status(employee, date):
	_guard_e2e()
	return frappe.db.get_value(
		"Attendance",
		{"employee": employee, "attendance_date": getdate(date)},
		["name", "status", "leave_type"],
		as_dict=True,
	)


@frappe.whitelist()
def create_dwl(
	employee=None,
	date=None,
	hours=6,
	project=None,
	submit=0,
	is_wfh=0,
	include_project=1,
	description="E2E daily work log task description here",
):
	_guard_e2e()
	employee = employee or _cast_employee("employee")
	user = frappe.session.user
	if user not in ("Administrator",) and not set(frappe.get_roles(user)).intersection(
		{"HR Manager", "HR User", "System Manager"}
	):
		session_emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if session_emp and employee != session_emp:
			frappe.throw(_("You can only create Daily Work Logs for yourself."))
	date = getdate(date or nowdate())
	project = project or get_or_create_project_with_cost_center()
	item = {
		"task_title": "E2E Task",
		"description": description,
		"time_spent_hours": flt(hours),
	}
	if cint(include_project):
		item["project"] = project
	doc = frappe.get_doc(
		{
			"doctype": "Daily Work Log",
			"employee": employee,
			"date": date,
			"is_wfh": cint(is_wfh),
			"items": [item],
		}
	)
	doc.insert(ignore_permissions=True)
	if cint(submit):
		doc.submit()
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus, "status": doc.status}


@frappe.whitelist()
def mark_dwl_reviewed(name, manager_remarks="Reviewed in E2E"):
	_guard_e2e()
	doc = frappe.get_doc("Daily Work Log", name)
	doc.mark_as_reviewed(manager_remarks)
	frappe.db.commit()
	return doc.status


@frappe.whitelist()
def cancel_dwl(name):
	_guard_e2e()
	doc = frappe.get_doc("Daily Work Log", name)
	if doc.docstatus == 1:
		doc.flags.ignore_permissions = True
		doc.cancel()
	frappe.db.commit()
	return doc.docstatus


@frappe.whitelist()
def trigger_attendance_job(attendance_date=None):
	_guard_e2e()
	from volunteering.volunteering.doctype.daily_work_log_settings.daily_work_log_settings import (
		trigger_attendance_job as _trigger,
	)

	return _trigger(attendance_date=attendance_date)


@frappe.whitelist()
def create_wfh_request(employee=None, date=None, submit=1):
	_guard_e2e()
	employee = employee or _cast_employee("employee")
	date = getdate(date or nowdate())
	doc = frappe.get_doc(
		{
			"doctype": "Attendance Request",
			"employee": employee,
			"from_date": date,
			"to_date": date,
			"half_day": 0,
			"reason": "Work From Home",
			"explanation": "E2E WFH request",
		}
	)
	doc.insert(ignore_permissions=True)
	if cint(submit):
		doc.submit()
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def approve_wfh(name):
	_guard_e2e()
	doc = frappe.get_doc("Attendance Request", name)
	employee_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if employee_user and frappe.session.user == employee_user:
		frappe.throw(_("Employees cannot approve their own attendance requests."))
	user = frappe.session.user
	if user != "Administrator" and not set(frappe.get_roles(user)).intersection(
		{"HR Manager", "HR User", "System Manager"}
	):
		manager_emp = frappe.db.get_value("Employee", {"user_id": user}, "name")
		if frappe.db.get_value("Employee", doc.employee, "reports_to") != manager_emp:
			frappe.throw(_("Only the reporting manager can approve this attendance request."))
	if doc.docstatus == 0:
		doc.flags.ignore_permissions = True
		doc.submit()
	else:
		doc.db_set("workflow_state", "Approved")
	doc.add_comment("Info", "Approved in E2E")
	frappe.db.commit()
	return {"name": doc.name, "docstatus": doc.docstatus}


@frappe.whitelist()
def create_leave_application(
	employee=None,
	category="Normal",
	from_date=None,
	to_date=None,
	leave_type=None,
	leave_approver=None,
	submit=0,
):
	_guard_e2e()
	employee = employee or _cast_employee("employee")
	from_date = getdate(from_date or add_days(nowdate(), 5))
	to_date = getdate(to_date or from_date)
	leave_type = leave_type or PRIVILEGE_LEAVE
	doc = frappe.get_doc(
		{
			"doctype": "Leave Application",
			"employee": employee,
			"leave_type": leave_type,
			"leave_category": category,
			"from_date": from_date,
			"to_date": to_date,
			"description": "E2E leave application",
			"leave_approver": leave_approver,
			"status": "Open",
		}
	)
	with _bypass_leave_access_check():
		doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def set_leave_status(name, status):
	_guard_e2e()
	doc = frappe.get_doc("Leave Application", name)
	session_emp = frappe.db.get_value("Employee", {"user_id": frappe.session.user}, "name")
	if session_emp and session_emp == doc.employee:
		doc.status = status
		doc.save()
		if doc.docstatus == 0:
			doc.submit()
		frappe.db.commit()
		return doc.status

	with _bypass_leave_access_check():
		doc.status = status
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
		if doc.docstatus == 0:
			doc.submit()
	frappe.db.commit()
	return doc.status


@frappe.whitelist()
def create_expense_claim(
	employee=None,
	amount=1500,
	submit=0,
	vendor_override_reason=None,
	budget_override_reason=None,
	include_project=1,
):
	_guard_e2e()
	employee = employee or _cast_employee("employee")
	project = get_or_create_project_with_cost_center() if cint(include_project) else None
	claim = make_expense_claim(
		employee,
		project,
		amount=flt(amount),
		vendor_override_reason=vendor_override_reason,
		budget_override_reason=budget_override_reason,
	)
	if cint(submit):
		_apply_workflow(claim, "Submit")
		claim.reload()
	frappe.db.commit()
	return {
		"name": claim.name,
		"workflow_state": claim.get("workflow_state"),
		"pending_approver": claim.get("pending_approver"),
	}


@frappe.whitelist()
def workflow_action(doctype, name, action):
	_guard_e2e()
	doc = frappe.get_doc(doctype, name)
	_apply_workflow(doc, action)
	doc.reload()
	frappe.db.commit()
	return {
		"name": doc.name,
		"workflow_state": doc.get("workflow_state"),
		"docstatus": doc.docstatus,
		"pending_approver": doc.get("pending_approver"),
	}


@frappe.whitelist()
def escalate_document(doctype, name, escalation_reason="E2E escalation"):
	_guard_e2e()
	from volunteering.volunteering.approval_routing import escalate_document as _escalate

	_escalate(doctype, name, escalation_reason=escalation_reason)
	doc = frappe.get_doc(doctype, name)
	frappe.db.commit()
	return {
		"name": doc.name,
		"workflow_state": doc.get("workflow_state"),
		"pending_approver": doc.get("pending_approver"),
	}


@frappe.whitelist()
def get_approver_flags(doctype, name):
	_guard_e2e()
	from volunteering.volunteering.approval_routing import get_approver_action_flags

	return get_approver_action_flags(doctype, name)


@frappe.whitelist()
def create_employee_advance(employee=None, amount=2000, submit=0):
	_guard_e2e()
	employee = employee or _cast_employee("employee")
	company = frappe.db.get_value("Employee", employee, "company")
	doc = frappe.get_doc(
		{
			"doctype": "Employee Advance",
			"employee": employee,
			"company": company,
			"purpose": "E2E advance",
			"advance_amount": flt(amount),
			"posting_date": nowdate(),
		}
	)
	doc.insert(ignore_permissions=True)
	if cint(submit):
		_apply_workflow(doc, "Submit")
		doc.reload()
	frappe.db.commit()
	return {"name": doc.name, "workflow_state": doc.get("workflow_state")}


@frappe.whitelist()
def set_advance_settlement(name, paid_amount=0, claimed_amount=0, status="Paid"):
	"""E2E-only: mark an advance paid/claimed without Payment Entry."""
	_guard_e2e()
	values = {
		"paid_amount": flt(paid_amount),
		"status": status,
	}
	if claimed_amount is not None:
		values["claimed_amount"] = flt(claimed_amount)
	frappe.db.set_value("Employee Advance", name, values, update_modified=False)
	frappe.db.commit()
	return True


@frappe.whitelist()
def create_purchase_order(amount=1500, submit=0):
	_guard_e2e()
	project = get_or_create_project_with_cost_center()
	with _allow_account_read():
		po = make_purchase_order(project, amount=flt(amount))
	if cint(submit):
		_apply_workflow(po, "Submit")
		po.reload()
	frappe.db.commit()
	return {"name": po.name, "workflow_state": po.get("workflow_state")}


@frappe.whitelist()
def create_purchase_invoice(po_name=None, amount=1500, submit=0):
	"""Create a PI. Omit po_name to hit the 'must link PO' rule on submit."""
	_guard_e2e()
	project = get_or_create_project_with_cost_center()
	with _skip_doc_perm_checks(), _allow_buying_read():
		if po_name:
			pi = make_purchase_invoice_from_po(po_name)
		else:
			pi = make_purchase_invoice(project, amount=flt(amount), purchase_order=None)
	if cint(submit):
		_apply_workflow(pi, "Submit")
		pi.reload()
	frappe.db.commit()
	return {
		"name": pi.name,
		"workflow_state": pi.get("workflow_state"),
		"docstatus": pi.docstatus,
		"outstanding_amount": flt(pi.get("outstanding_amount")),
	}


@frappe.whitelist()
def try_create_purchase_invoice(**kwargs):
	_guard_e2e()
	try:
		return {"ok": True, "data": create_purchase_invoice(**_strip_rpc_kwargs(kwargs))}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def create_supplier_payment_entry(reference_doctype, reference_name, submit=0):
	_guard_e2e()
	roles = set(frappe.get_roles())
	if not roles.intersection({"Accounts Manager", "Accounts User", "System Manager"}):
		frappe.throw(
			_("Only Accounts can create vendor Payment Entries."),
			frappe.PermissionError,
		)
	with _skip_doc_perm_checks(), _allow_buying_read():
		pe = make_supplier_payment_entry(reference_doctype, reference_name)
	if cint(submit):
		pe.flags.ignore_permissions = True
		with _skip_doc_perm_checks(), _allow_buying_read():
			pe.submit()
		pe.reload()
	frappe.db.commit()
	return {
		"name": pe.name,
		"docstatus": pe.docstatus,
		"party_type": pe.party_type,
		"paid_amount": flt(pe.paid_amount),
	}


@frappe.whitelist()
def try_create_supplier_payment_entry(**kwargs):
	_guard_e2e()
	try:
		return {
			"ok": True,
			"data": create_supplier_payment_entry(**_strip_rpc_kwargs(kwargs)),
		}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def mark_invoice_paid_outside(name, remarks="E2E paid outside"):
	_guard_e2e()
	from volunteering.volunteering.reimbursement_controls import (
		mark_purchase_invoice_paid_outside,
	)

	roles = set(frappe.get_roles())
	if not roles.intersection({"Accounts Manager", "Accounts User", "System Manager"}):
		frappe.throw(_("Only Accounts can mark invoices paid outside the system."), frappe.PermissionError)

	with _skip_doc_perm_checks(), _allow_buying_read():
		pe_name = mark_purchase_invoice_paid_outside(name, remarks=remarks)
	frappe.db.commit()
	return {"payment_entry": pe_name}


@frappe.whitelist()
def try_mark_invoice_paid_outside(**kwargs):
	_guard_e2e()
	try:
		return {"ok": True, "data": mark_invoice_paid_outside(**_strip_rpc_kwargs(kwargs))}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def set_single_setting(doctype, field, value):
	_guard_e2e()
	frappe.db.set_single_value(doctype, field, value)
	frappe.db.commit()
	return True


@frappe.whitelist()
def get_doc_field(doctype, name, field):
	_guard_e2e()
	return frappe.db.get_value(doctype, name, field)


@frappe.whitelist()
def set_employee_field(employee, field, value):
	_guard_e2e()
	frappe.db.set_value("Employee", employee, field, value)
	frappe.db.commit()
	return True


@frappe.whitelist()
def create_manager_note(employee, note_type="Appreciation", content="E2E note"):
	_guard_e2e()
	doc = frappe.get_doc(
		{
			"doctype": "Manager Note",
			"employee": employee,
			"note_type": note_type,
			"content": content,
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return doc.name


@frappe.whitelist()
def set_employee_reports_to(employee, reports_to):
	_guard_e2e()
	doc = frappe.get_doc("Employee", employee)
	doc.reports_to = reports_to or None
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return frappe.db.get_value("Employee", employee, "leave_approver")


@frappe.whitelist()
def create_regularization(employee, attendance_date, requested_status="Present", reason="E2E regularization"):
	_guard_e2e()
	doc = frappe.get_doc(
		{
			"doctype": "Attendance Regularization Request",
			"employee": employee,
			"attendance_date": getdate(attendance_date),
			"requested_status": requested_status,
			"reason": reason,
			"status": "Open",
		}
	)
	doc.insert(ignore_permissions=True)
	frappe.db.commit()
	return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def approve_regularization(name):
	_guard_e2e()
	doc = frappe.get_doc("Attendance Regularization Request", name)
	doc.approve_request()
	frappe.db.commit()
	return doc.status


@frappe.whitelist()
def reject_regularization(name):
	_guard_e2e()
	doc = frappe.get_doc("Attendance Regularization Request", name)
	doc.reject_request()
	frappe.db.commit()
	return doc.status


@frappe.whitelist()
def cancel_wfh(name):
	_guard_e2e()
	from volunteering.volunteering.attendance_request_permissions import (
		before_cancel_attendance_request,
	)

	doc = frappe.get_doc("Attendance Request", name)
	if doc.docstatus == 1:
		before_cancel_attendance_request(doc)
		doc.flags.ignore_permissions = True
		frappe.flags.ignore_permissions = True
		try:
			doc.cancel()
		finally:
			frappe.flags.ignore_permissions = False
	frappe.db.commit()
	return doc.docstatus


@frappe.whitelist()
def try_create_dwl(**kwargs):
	"""Same as create_dwl but returns {ok, error} instead of throwing."""
	_guard_e2e()
	try:
		return {"ok": True, "data": create_dwl(**_strip_rpc_kwargs(kwargs))}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def try_create_leave(**kwargs):
	_guard_e2e()
	try:
		return {"ok": True, "data": create_leave_application(**_strip_rpc_kwargs(kwargs))}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def try_create_advance(**kwargs):
	_guard_e2e()
	try:
		return {"ok": True, "data": create_employee_advance(**_strip_rpc_kwargs(kwargs))}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def try_create_expense_claim(**kwargs):
	_guard_e2e()
	try:
		return {"ok": True, "data": create_expense_claim(**_strip_rpc_kwargs(kwargs))}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def try_workflow_action(doctype, name, action):
	_guard_e2e()
	try:
		return {"ok": True, "data": workflow_action(doctype, name, action)}
	except Exception as exc:
		frappe.db.rollback()
		return {"ok": False, "error": _exc_message(exc)}


@frappe.whitelist()
def preview_work_log_digest():
	_guard_e2e()
	from volunteering.volunteering.api.attendance_digest import preview_work_log_digest

	return preview_work_log_digest()


@frappe.whitelist()
def set_project_budget(project, department, allocated_amount):
	_guard_e2e()
	set_project_department_budget(project, department, flt(allocated_amount))
	frappe.db.commit()
	return True
