# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Independent receipt review gate for Expense Claims.

Receipt reviewers can inspect a claim and its private attachments, but the only
write path exposed to them is :func:`review_receipts`.  Manager approval and
employee reimbursement are both rejected unless the reviewed attachment
snapshot still matches the claim.
"""

from __future__ import annotations

import json
from pathlib import PurePosixPath

import frappe
from frappe import _
from frappe.utils import now_datetime

RECEIPT_REVIEWER_ROLE = "Expense Receipt Reviewer"
PENDING_RECEIPT_REVIEW = "Pending Receipt Review"
RECEIPT_CORRECTION_REQUIRED = "Receipt Correction Required"

REVIEW_STATUS_NOT_SUBMITTED = "Not Submitted"
REVIEW_STATUS_PENDING = "Pending Review"
REVIEW_STATUS_VERIFIED = "Verified"
REVIEW_STATUS_CORRECTION_REQUIRED = "Correction Required"

ALLOWED_RECEIPT_EXTENSIONS = frozenset({".pdf", ".png", ".jpg", ".jpeg"})


def _receipt_files(claim_name: str) -> list[frappe._dict]:
	return frappe.get_all(
		"File",
		filters={
			"attached_to_doctype": "Expense Claim",
			"attached_to_name": claim_name,
		},
		fields=["name", "file_name", "file_url", "file_size", "content_hash", "is_private"],
		order_by="name asc",
	)


def _validate_receipt_files(claim_name: str) -> list[frappe._dict]:
	files = _receipt_files(claim_name)
	if not files:
		frappe.throw(_("Attach at least one receipt before submitting the expense claim."))

	invalid = []
	public = []
	for row in files:
		extension = PurePosixPath(row.file_name or row.file_url or "").suffix.lower()
		if extension not in ALLOWED_RECEIPT_EXTENSIONS:
			invalid.append(row.file_name or row.name)
		if not row.is_private:
			public.append(row.file_name or row.name)

	if invalid:
		frappe.throw(
			_("Receipts must be PDF, PNG, JPG, or JPEG files. Unsupported: {0}").format(", ".join(invalid))
		)
	if public:
		frappe.throw(
			_("Receipts must be uploaded as private files. Public files: {0}").format(", ".join(public))
		)
	return files


def _attachment_snapshot(files: list[frappe._dict]) -> str:
	rows = [
		{
			"file": row.name,
			"file_name": row.file_name,
			"file_url": row.file_url,
			"file_size": row.file_size,
			"content_hash": row.content_hash,
		}
		for row in files
	]
	return json.dumps(rows, sort_keys=True, separators=(",", ":"))


def _assert_reviewer(user: str):
	if user == "Administrator":
		return
	if RECEIPT_REVIEWER_ROLE not in frappe.get_roles(user):
		frappe.throw(
			_("Only an Expense Receipt Reviewer can perform receipt review."),
			frappe.PermissionError,
		)


def _assert_not_own_claim(doc, user: str):
	from volunteering.volunteering.approval_routing import get_requester_user

	if user != "Administrator" and get_requester_user(doc) == user:
		frappe.throw(_("You cannot review receipts for your own expense claim."))


def prepare_receipt_review_on_save(doc, method=None):
	"""Initialise/reset review data when an employee submits or re-submits."""
	if doc.doctype != "Expense Claim":
		return

	previous = doc.get_doc_before_save()
	previous_state = previous.workflow_state if previous else None
	if doc.workflow_state == PENDING_RECEIPT_REVIEW and previous_state != PENDING_RECEIPT_REVIEW:
		if doc.is_new():
			frappe.throw(_("Save the expense claim and attach receipts before submitting."))
		_validate_receipt_files(doc.name)
		doc.receipt_review_status = REVIEW_STATUS_PENDING
		doc.receipt_reviewed_by = None
		doc.receipt_reviewed_on = None
		doc.receipt_review_notes = None
		doc.receipt_review_checklist = None
		doc.reviewed_attachments = None
		doc.pending_approver = None
		doc.expense_approver = None

	if previous_state == PENDING_RECEIPT_REVIEW and not getattr(doc.flags, "receipt_review_action", False):
		frappe.throw(
			_(
				"This claim is awaiting receipt review and cannot be edited. "
				"The reviewer must Verify Receipts or Request Correction."
			)
		)


def validate_verified_receipts(doc, method=None):
	"""Require an intact verified snapshot before manager approval/submission."""
	if doc.doctype != "Expense Claim":
		return
	if doc.workflow_state not in ("Pending Approval", "Pending Accounts Classification", "Approved"):
		return
	if doc.get("receipt_review_status") != REVIEW_STATUS_VERIFIED:
		frappe.throw(_("Receipt review must be Verified before manager approval."))
	files = _validate_receipt_files(doc.name)
	if doc.get("reviewed_attachments") != _attachment_snapshot(files):
		frappe.throw(_("Receipts changed after verification. Send the claim through receipt review again."))


def _manager_routing_values(doc) -> dict:
	from volunteering.volunteering.approval_routing import (
		assign_expense_approver,
		assign_pending_approver,
		get_effective_approval_level,
		use_grade_approval,
	)

	if use_grade_approval():
		doc.approval_level = 1
		assign_pending_approver(doc)
	else:
		doc.approval_level = get_effective_approval_level(doc)
	assign_expense_approver(doc)
	if not doc.get("pending_approver") and doc.get("expense_approver"):
		doc.pending_approver = doc.expense_approver
	if not doc.get("pending_approver"):
		frappe.throw(_("No manager approver could be resolved for this expense claim."))
	return {
		"approval_level": doc.approval_level,
		"pending_approver": doc.pending_approver,
		"expense_approver": doc.expense_approver,
	}


@frappe.whitelist(methods=["POST"])
def review_receipts(name: str, decision: str, notes: str = "", checklist=None):
	"""Verify attached receipts or send the draft back to its employee.

	``checklist`` is an ignored compatibility argument for older clients. The
	review decision, notes, reviewer, timestamp and attachment snapshot form the
	receipt-review audit record.
	"""
	user = frappe.session.user
	_assert_reviewer(user)
	doc = frappe.get_doc("Expense Claim", name)
	doc.check_permission("read")
	_assert_not_own_claim(doc, user)
	legacy_approved = (
		doc.docstatus == 1
		and doc.workflow_state == "Approved"
		and doc.get("receipt_review_status") != REVIEW_STATUS_VERIFIED
	)
	if not legacy_approved and (doc.docstatus != 0 or doc.workflow_state != PENDING_RECEIPT_REVIEW):
		frappe.throw(_("This expense claim is not awaiting receipt review."))

	decision = (decision or "").strip().lower()
	notes = (notes or "").strip()
	files = _validate_receipt_files(doc.name)
	now = now_datetime()
	values = {
		"receipt_reviewed_by": user,
		"receipt_reviewed_on": now,
		"receipt_review_notes": notes,
		"receipt_review_checklist": None,
		"reviewed_attachments": _attachment_snapshot(files),
	}

	if decision == "verify":
		values["receipt_review_status"] = REVIEW_STATUS_VERIFIED
		if legacy_approved:
			comment = _("Legacy approved claim receipts retrospectively verified by {0}.").format(user)
		else:
			values.update(_manager_routing_values(doc))
			values["workflow_state"] = "Pending Approval"
			comment = _("Receipts verified by {0}. Manager approval is now pending.").format(user)
	elif decision == "request_correction":
		if legacy_approved:
			frappe.throw(
				_(
					"This claim was approved before receipt review was introduced. "
					"Cancel and amend it if the receipt needs correction."
				)
			)
		if not notes:
			frappe.throw(_("Correction notes are required."))
		values.update(
			{
				"workflow_state": RECEIPT_CORRECTION_REQUIRED,
				"receipt_review_status": REVIEW_STATUS_CORRECTION_REQUIRED,
				"pending_approver": None,
				"expense_approver": None,
			}
		)
		comment = _("Receipt correction requested by {0}: {1}").format(user, notes)
	else:
		frappe.throw(_("Decision must be Verify or Request Correction."))

	frappe.db.set_value("Expense Claim", doc.name, values)
	doc.reload()
	doc.add_comment("Workflow", comment)
	if decision == "verify" and not legacy_approved:
		from volunteering.volunteering.approval_routing import notify_pending_approvers

		notify_pending_approvers(doc)
	elif decision == "request_correction":
		_notify_employee_correction(doc, notes)
	return doc.as_dict()


def _notify_employee_correction(doc, notes: str):
	from volunteering.volunteering.approval_routing import get_requester_user

	recipient = get_requester_user(doc)
	if not recipient or recipient in ("Guest", "Administrator"):
		return
	link = frappe.utils.get_url(f"/volunteering/expense-claim?correct={doc.name}")
	frappe.sendmail(
		recipients=[recipient],
		subject=_("Receipt correction required: Expense Claim {0}").format(doc.name),
		message=_('Your expense claim <a href="{0}">{1}</a> needs receipt correction.<br><br>{2}').format(
			link, doc.name, frappe.utils.escape_html(notes)
		),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)


def notify_receipt_reviewers(doc):
	"""Alert enabled reviewers when a claim enters the review queue."""
	recipients = frappe.get_all(
		"Has Role",
		filters={
			"role": RECEIPT_REVIEWER_ROLE,
			"parenttype": "User",
			"parent": ["not in", ["Guest", doc.owner]],
		},
		pluck="parent",
	)
	recipients = [user for user in sorted(set(recipients)) if frappe.db.get_value("User", user, "enabled")]
	if not recipients:
		return
	link = frappe.utils.get_url(f"/volunteering/expense-claim-workflow?claim={doc.name}")
	frappe.sendmail(
		recipients=recipients,
		subject=_("Receipt review required: Expense Claim {0}").format(doc.name),
		message=_('Expense Claim <a href="{0}">{1}</a> is awaiting receipt review.').format(link, doc.name),
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)


def validate_receipt_file_change(file_doc, method=None):
	"""Approved claims retain immutable audit evidence."""
	if file_doc.get("attached_to_doctype") != "Expense Claim" or not file_doc.get("attached_to_name"):
		return
	claim = frappe.db.get_value(
		"Expense Claim",
		file_doc.attached_to_name,
		["docstatus", "workflow_state"],
		as_dict=True,
	)
	if claim and claim.docstatus == 1:
		frappe.throw(
			_(
				"Receipts cannot be added, replaced, or deleted after manager approval. "
				"Cancel and amend the expense claim instead."
			)
		)


def reset_review_after_file_change(file_doc, method=None):
	"""Any attachment mutation before approval invalidates prior verification."""
	if file_doc.get("attached_to_doctype") != "Expense Claim" or not file_doc.get("attached_to_name"):
		return
	name = file_doc.attached_to_name
	claim = frappe.db.get_value(
		"Expense Claim",
		name,
		["docstatus", "workflow_state", "receipt_review_status"],
		as_dict=True,
	)
	if not claim or claim.docstatus != 0:
		return
	if claim.receipt_review_status != REVIEW_STATUS_VERIFIED:
		return

	frappe.db.set_value(
		"Expense Claim",
		name,
		{
			"workflow_state": PENDING_RECEIPT_REVIEW,
			"receipt_review_status": REVIEW_STATUS_PENDING,
			"receipt_reviewed_by": None,
			"receipt_reviewed_on": None,
			"receipt_review_notes": None,
			"receipt_review_checklist": None,
			"reviewed_attachments": None,
			"pending_approver": None,
			"expense_approver": None,
		},
	)
	frappe.get_doc("Expense Claim", name).add_comment(
		"Workflow", _("Receipt review reset because an attachment changed.")
	)


@frappe.whitelist()
def get_receipt_review_action_flags(name: str):
	doc = frappe.get_doc("Expense Claim", name)
	doc.check_permission("read")
	user = frappe.session.user
	roles = set(frappe.get_roles(user))
	legacy_approved = (
		doc.docstatus == 1
		and doc.workflow_state == "Approved"
		and doc.get("receipt_review_status") != REVIEW_STATUS_VERIFIED
	)
	can_review = (
		(user == "Administrator" or RECEIPT_REVIEWER_ROLE in roles)
		and ((doc.docstatus == 0 and doc.workflow_state == PENDING_RECEIPT_REVIEW) or legacy_approved)
		and user != _requester_user(doc)
	)
	return {
		"can_review": can_review,
		"can_request_correction": can_review and not legacy_approved,
	}


def _requester_user(doc) -> str | None:
	from volunteering.volunteering.approval_routing import get_requester_user

	return get_requester_user(doc)
