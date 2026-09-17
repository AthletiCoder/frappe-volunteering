"""Private, visibility-scoped project evidence published only through approval."""

from contextlib import contextmanager
from contextvars import ContextVar

import frappe
from frappe import _
from frappe.core.doctype.file.file import File
from frappe.utils import cint

from volunteering.volunteering import project_workspace as workspace

_writing = ContextVar("project_evidence_write", default=False)


@contextmanager
def writing():
	token = _writing.set(True)
	try:
		yield
	finally:
		_writing.reset(token)


def scoped(file):
	return file.attached_to_doctype in ("Project", "Project Proposal") and file.attached_to_name


def can_read(file, user=None):
	from volunteering.volunteering.employee_bank_accounts import can_read_file, scoped_file

	if scoped_file(file):
		return can_read_file(file, user)
	if not scoped(file):
		return True
	user = user or frappe.session.user
	if user == "Guest":
		return False
	parent = frappe.get_doc(file.attached_to_doctype, file.attached_to_name)
	if parent.doctype == "Project":
		return workspace._can_view(parent, user) and (
			file.get("project_visibility") == "Basic" or workspace.can_view_finance(parent, user)
		)
	from volunteering.volunteering.project_proposals import _readable

	if not _readable(parent, user):
		return False
	if file.get("project_visibility") == "Basic" or workspace.is_project_manager(user):
		return True
	return parent.request_kind == "New Project" or workspace.can_view_finance(
		frappe.get_doc("Project", parent.project), user
	)


def has_permission(doc, user=None, ptype=None, **kwargs):
	from volunteering.volunteering.employee_bank_accounts import scoped_file

	if scoped_file(doc):
		return ptype in ("read", "select") and can_read(doc, user)
	if scoped(doc):
		return ptype in ("read", "select", "print") and can_read(doc, user)
	return None


def validate_change(doc, method=None):
	previous = doc.get_doc_before_save()
	if scoped(doc) or (previous and scoped(previous)):
		if not _writing.get():
			frappe.throw(
				_("Project evidence is changed through a proposal, not directly on the approved project."),
				frappe.PermissionError,
			)
		if not cint(doc.is_private):
			frappe.throw(_("Project evidence must be stored privately."))
		if doc.get("project_visibility") not in ("Basic", "Financial"):
			frappe.throw(_("Choose Basic or Financial document visibility."))


class ProjectAwareFile(File):
	def is_downloadable(self):
		return can_read(self) and super().is_downloadable()

	def get_content(self, encodings=None):
		from volunteering.volunteering.employee_bank_accounts import scoped_file

		if (scoped(self) or scoped_file(self)) and not _writing.get() and not can_read(self):
			frappe.throw(_("You cannot download this project document."), frappe.PermissionError)
		return super().get_content(encodings)


def list_documents(doctype, name):
	return [
		row
		for row in frappe.get_all(
			"File",
			filters={"attached_to_doctype": doctype, "attached_to_name": name},
			fields=["name", "file_name", "file_url", "is_private", "project_visibility"],
		)
		if can_read(frappe.get_doc("File", row.name))
	]


def publish(doc):
	# Retain originals on the immutable request; new private attachment records
	# publish the approved evidence to current project membership.
	from frappe.utils.file_manager import save_file

	with writing():
		for row in list_documents("Project Proposal", doc.name):
			file = frappe.get_doc("File", row.name)
			created = save_file(file.file_name, file.get_content(), "Project", doc.project, is_private=1)
			created.project_visibility = file.project_visibility
			created.save(ignore_permissions=True)


def file_query(user=None):
	user = user or frappe.session.user
	from volunteering.volunteering.employee_bank_accounts import _is_accounts_manager

	bank_scope = (
		"1=1"
		if _is_accounts_manager(user)
		else (
			f"(`tabFile`.attached_to_doctype IS NULL OR `tabFile`.attached_to_doctype != 'Employee Bank Account Request' "
			f"OR EXISTS (SELECT 1 FROM `tabEmployee Bank Account Request` b WHERE b.name=`tabFile`.attached_to_name AND b.submitted_by={frappe.db.escape(user)}))"
		)
	)
	if workspace.is_project_manager(user):
		return bank_scope
	escaped = frappe.db.escape(user)
	finance = (
		"1=1"
		if workspace.FINANCE_READ_ROLES.intersection(workspace._roles(user))
		else f"EXISTS (SELECT 1 FROM `tabProject Participant` pm WHERE pm.parent=p.name AND pm.parenttype='Project' AND pm.user={escaped} AND pm.access_level='Financial')"
	)
	view = (
		"1=1"
		if workspace._can_oversee(user)
		else f"(p.owner={escaped} OR p.project_owner={escaped} OR p.project_proposed_by={escaped} OR EXISTS (SELECT 1 FROM `tabProject Participant` pm WHERE pm.parent=p.name AND pm.parenttype='Project' AND pm.user={escaped}))"
	)
	return f"""{bank_scope} AND (`tabFile`.attached_to_doctype NOT IN ('Project', 'Project Proposal') OR `tabFile`.attached_to_doctype IS NULL
	 OR (`tabFile`.attached_to_doctype='Project' AND EXISTS (SELECT 1 FROM `tabProject` p WHERE p.name=`tabFile`.attached_to_name AND {view} AND (`tabFile`.project_visibility='Basic' OR {finance})))
	 OR (`tabFile`.attached_to_doctype='Project Proposal' AND EXISTS (SELECT 1 FROM `tabProject Proposal` r WHERE r.name=`tabFile`.attached_to_name AND r.proposed_by={escaped}
	 AND (`tabFile`.project_visibility='Basic' OR r.request_kind='New Project' OR EXISTS (SELECT 1 FROM `tabProject` p WHERE p.name=r.project AND {finance})))))"""
