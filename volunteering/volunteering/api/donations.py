"""Guest-facing donation APIs for Cashfree + ERPNext."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from volunteering.volunteering.api import cashfree_client
from volunteering.volunteering.api.payment_entry import create_payment_entry_for_donation
from volunteering.volunteering.api.volunteer_donor import upsert_volunteer_for_donation
from volunteering.volunteering.doctype.cashfree_settings.cashfree_settings import (
	get_cashfree_settings,
)
from volunteering.volunteering.doctype.volunteer.volunteer import (
	find_volunteer_by_mobile,
	format_mobile_number,
)

PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
ORDER_STATUS_PAID = {"PAID", "SUCCESS"}
ORDER_STATUS_FAILED = {"FAILED", "EXPIRED", "CANCELLED", "TERMINATED"}


def _apply_cors():
	origin = frappe.get_request_header("Origin")
	if not origin:
		return
	settings = frappe.get_cached_doc("Cashfree Settings")
	allowed = [
		o.strip()
		for o in (settings.allowed_origins or "").replace("\n", ",").split(",")
		if o.strip()
	]
	if origin in allowed or "*" in allowed:
		frappe.local.response["headers"] = frappe.local.response.get("headers") or {}
		# Frappe uses local.response_headers in newer versions
		try:
			frappe.local.response_headers["Access-Control-Allow-Origin"] = origin
			frappe.local.response_headers["Access-Control-Allow-Credentials"] = "true"
			frappe.local.response_headers["Access-Control-Allow-Headers"] = (
				"Content-Type, Authorization, X-Frappe-CSRF-Token, X-Requested-With"
			)
			frappe.local.response_headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
		except Exception:
			pass


def _make_status_token(donation_name: str) -> str:
	secret = frappe.utils.cstr(frappe.local.conf.get("encryption_key") or "volunteering-donations")
	digest = hmac.new(
		secret.encode("utf-8"),
		donation_name.encode("utf-8"),
		hashlib.sha256,
	).hexdigest()
	return digest[:32]


def _assert_status_token(donation_name: str, token: str | None):
	expected = _make_status_token(donation_name)
	if not token or not hmac.compare_digest(expected, str(token)):
		frappe.throw(_("Invalid status token"), frappe.PermissionError)


def _check_fraud_limits(*, mobile: str, amount: float, settings):
	min_amount = flt(settings.min_amount or 100)
	max_amount = flt(settings.max_amount_per_txn or 500000)
	if amount < min_amount:
		frappe.throw(_(f"Minimum donation amount is ₹{min_amount:g}"))
	if amount > max_amount:
		frappe.throw(_(f"Maximum donation amount is ₹{max_amount:g}"))

	formatted = format_mobile_number(mobile)
	max_per_hour = cint(settings.max_txns_per_phone_per_hour or 10)
	if formatted and max_per_hour > 0:
		count = frappe.db.count(
			"Donation",
			{
				"mobile_number": formatted,
				"creation": (">=", frappe.utils.add_to_date(None, hours=-1, as_datetime=True)),
			},
		)
		if count >= max_per_hour:
			frappe.throw(_("Too many donation attempts. Please try again later."))

	# Soft IP rate limit (create path only)
	ip = frappe.local.request_ip if hasattr(frappe.local, "request_ip") else None
	if ip:
		ip_count = frappe.db.count(
			"Donation",
			{
				"ip_address": ip,
				"creation": (">=", frappe.utils.add_to_date(None, hours=-1, as_datetime=True)),
			},
		)
		if ip_count >= max(max_per_hour * 3, 30):
			frappe.throw(_("Too many requests from this network. Please try again later."))


def _resolve_referred_by(ref: str | None) -> str | None:
	if not ref:
		return None
	ref = str(ref).strip()
	if frappe.db.exists("Volunteer", ref):
		return ref
	by_mobile = find_volunteer_by_mobile(ref)
	return by_mobile


def _request_args(**kwargs) -> dict:
	"""Merge JSON body and form_dict for guest API calls from React."""
	data = {}
	if frappe.request:
		json_body = frappe.request.get_json(silent=True)
		if isinstance(json_body, dict):
			data.update(json_body)
	data.update(dict(frappe.form_dict or {}))
	data.update({k: v for k, v in kwargs.items() if v is not None})
	data.pop("cmd", None)
	return data


@frappe.whitelist(allow_guest=True)
def create_donation_and_order(**kwargs):
	"""
	Create Donation + Cashfree order. Returns payment_session_id for JS checkout.
	"""
	_apply_cors()
	settings = get_cashfree_settings()
	kwargs = _request_args(**kwargs)

	full_name = (kwargs.get("full_name") or kwargs.get("donor_name") or "").strip()
	email = (kwargs.get("email") or "").strip().lower()
	mobile = kwargs.get("mobile_number") or kwargs.get("phone") or ""
	amount = flt(kwargs.get("amount"))
	want_80g = cint(kwargs.get("want_80g") or kwargs.get("want80g") or 0)
	pan = (kwargs.get("pan") or "").strip().upper()
	address = (kwargs.get("address") or "").strip()
	ref = kwargs.get("ref") or kwargs.get("ref_id") or kwargs.get("referred_by")
	return_url = kwargs.get("return_url") or settings.return_url

	if not full_name:
		frappe.throw(_("Full name is required"))
	if not email or "@" not in email:
		frappe.throw(_("Valid email is required"))
	if not format_mobile_number(mobile):
		frappe.throw(_("Valid mobile number is required"))

	_check_fraud_limits(mobile=mobile, amount=amount, settings=settings)

	if want_80g:
		if not PAN_RE.match(pan):
			frappe.throw(_("Valid PAN is required for 80G"))
		if not address:
			frappe.throw(_("Address is required for 80G"))

	volunteer_name, matched_existing = upsert_volunteer_for_donation(
		full_name=full_name,
		mobile_number=mobile,
		email=email,
		pan=pan if want_80g else None,
		address=address if want_80g else None,
	)

	donation = frappe.new_doc("Donation")
	donation.full_name = full_name
	donation.email = email
	donation.mobile_number = format_mobile_number(mobile)
	donation.amount = amount
	donation.currency = "INR"
	donation.want_80g = want_80g
	donation.pan = pan if want_80g else ""
	donation.address = address if want_80g else ""
	donation.volunteer = volunteer_name
	donation.referred_by = _resolve_referred_by(ref)
	donation.source = "Gateway"
	donation.status = "Initiated"
	donation.ip_address = getattr(frappe.local, "request_ip", None)
	donation.user_agent = frappe.get_request_header("User-Agent")
	donation.insert(ignore_permissions=True)

	status_token = _make_status_token(donation.name)
	donation.db_set("status_token", status_token, update_modified=False)

	order_id = donation.name.replace(" ", "-")
	resolved_return = None
	if return_url:
		resolved_return = return_url.replace("{order_id}", order_id).replace(
			"{donation_id}", donation.name
		)
		if "status_token" not in resolved_return and "?" in resolved_return:
			resolved_return = f"{resolved_return}&status_token={status_token}"
		elif "status_token" not in resolved_return:
			resolved_return = f"{resolved_return}?donation_id={donation.name}&status_token={status_token}"

	order = cashfree_client.create_order(
		order_id=order_id,
		amount=amount,
		customer_id=volunteer_name,
		customer_phone=donation.mobile_number,
		customer_email=email,
		customer_name=full_name,
		return_url=resolved_return,
	)

	session_id = order.get("payment_session_id")
	donation.db_set(
		{
			"cashfree_order_id": order.get("order_id") or order_id,
			"payment_session_id": session_id,
			"status": "Pending",
		},
		update_modified=False,
	)

	matched_name = None
	if matched_existing:
		matched_name = frappe.db.get_value(
			"Volunteer", volunteer_name, ["first_name", "last_name"], as_dict=True
		)
		if matched_name:
			matched_name = f"{matched_name.first_name or ''} {matched_name.last_name or ''}".strip()

	return {
		"donation_id": donation.name,
		"order_id": order.get("order_id") or order_id,
		"payment_session_id": session_id,
		"status_token": status_token,
		"environment": settings.environment,
		"volunteer": volunteer_name,
		"matched_existing_volunteer": matched_existing,
		"matched_volunteer_name": matched_name,
		"amount": amount,
	}


@frappe.whitelist(allow_guest=True)
def get_donation_status(donation_id: str | None = None, status_token: str | None = None, **kwargs):
	_apply_cors()
	kwargs = _request_args(donation_id=donation_id, status_token=status_token, **kwargs)
	donation_id = kwargs.get("donation_id") or kwargs.get("docname")
	status_token = kwargs.get("status_token") or kwargs.get("token")
	if not donation_id:
		frappe.throw(_("donation_id is required"))

	_assert_status_token(donation_id, status_token)
	donation = frappe.get_doc("Donation", donation_id)

	# Soft refresh from Cashfree if still pending
	if donation.status in ("Initiated", "Pending") and donation.cashfree_order_id:
		try:
			_sync_donation_from_order(donation)
			donation.reload()
		except Exception:
			frappe.log_error(frappe.get_traceback(), "Donation status refresh failed")

	return {
		"donation_id": donation.name,
		"status": donation.status,
		"amount": donation.amount,
		"full_name": donation.full_name,
		"want_80g": cint(donation.want_80g),
		"payment_entry": donation.payment_entry,
	}


@frappe.whitelist(allow_guest=True)
def get_donation_receipt_payload(
	donation_id: str | None = None, status_token: str | None = None, **kwargs
):
	_apply_cors()
	kwargs = _request_args(donation_id=donation_id, status_token=status_token, **kwargs)
	donation_id = kwargs.get("donation_id")
	status_token = kwargs.get("status_token") or kwargs.get("token")
	if not donation_id:
		frappe.throw(_("donation_id is required"))

	_assert_status_token(donation_id, status_token)
	donation = frappe.get_doc("Donation", donation_id)
	settings = frappe.get_single("Cashfree Settings")

	return {
		"donation_id": donation.name,
		"status": donation.status,
		"amount": donation.amount,
		"currency": donation.currency,
		"full_name": donation.full_name,
		"email": donation.email,
		"mobile_number": donation.mobile_number,
		"want_80g": cint(donation.want_80g),
		"pan": donation.pan if donation.want_80g else None,
		"cf_payment_id": donation.cf_payment_id,
		"cashfree_order_id": donation.cashfree_order_id,
		"org_display_name": settings.org_display_name,
		"eighty_g_registration_number": settings.eighty_g_registration_number,
		"twelve_a_registration_number": settings.twelve_a_registration_number,
		"acknowledgement_note": (
			"This is an acknowledgement of your donation. "
			"Formal Form 10BE (if 80G was requested) is issued after annual Form 10BD filing."
			if donation.want_80g
			else "Thank you for your donation."
		),
	}


@frappe.whitelist(allow_guest=True, methods=["POST"])
def cashfree_webhook():
	"""Cashfree payment webhook — signature verified, idempotent Success handling."""
	raw = frappe.request.get_data(as_text=True) or ""
	timestamp = frappe.get_request_header("x-webhook-timestamp") or ""
	signature = frappe.get_request_header("x-webhook-signature") or ""

	settings = get_cashfree_settings()
	secret = settings.get_password("webhook_secret", raise_exception=False) or settings.get_password(
		"secret_key"
	)
	if not _verify_webhook_signature(secret, timestamp, raw, signature):
		frappe.throw(_("Invalid webhook signature"), frappe.AuthenticationError)

	try:
		payload = json.loads(raw) if raw else {}
	except json.JSONDecodeError:
		frappe.throw(_("Invalid webhook payload"))

	_process_webhook_payload(payload)
	return {"ok": True}


def _verify_webhook_signature(secret: str, timestamp: str, raw_body: str, signature: str) -> bool:
	if not secret or not timestamp or not signature:
		return False
	message = f"{timestamp}{raw_body}".encode("utf-8")
	digest = hmac.new(secret.encode("utf-8"), message, hashlib.sha256).digest()
	computed = base64.b64encode(digest).decode("utf-8")
	return hmac.compare_digest(computed, signature)


def _process_webhook_payload(payload: dict[str, Any]):
	data = payload.get("data") or {}
	order = data.get("order") or {}
	payment = data.get("payment") or {}

	order_id = order.get("order_id") or payload.get("order_id")
	if not order_id:
		# Some payloads nest differently
		order_id = (data.get("order_id") if isinstance(data, dict) else None) or None

	if not order_id:
		frappe.log_error(title="Cashfree webhook missing order_id", message=str(payload)[:2000])
		return

	donation_name = frappe.db.get_value("Donation", {"cashfree_order_id": order_id}, "name")
	if not donation_name and frappe.db.exists("Donation", order_id):
		donation_name = order_id

	if not donation_name:
		frappe.log_error(
			title="Cashfree webhook unknown order",
			message=f"order_id={order_id} payload={str(payload)[:1500]}",
		)
		return

	donation = frappe.get_doc("Donation", donation_name)
	order_status = (order.get("order_status") or payment.get("payment_status") or "").upper()
	event_type = (payload.get("type") or "").upper()

	cf_payment_id = payment.get("cf_payment_id") or payment.get("payment_id")
	if cf_payment_id:
		donation.db_set("cf_payment_id", cf_payment_id, update_modified=False)

	is_success = (
		order_status in ORDER_STATUS_PAID
		or "PAYMENT_SUCCESS" in event_type
		or (payment.get("payment_status") or "").upper() in ORDER_STATUS_PAID
	)
	is_failed = (
		order_status in ORDER_STATUS_FAILED
		or "PAYMENT_FAILED" in event_type
		or "USER_DROPPED" in event_type
		or (payment.get("payment_status") or "").upper() in ORDER_STATUS_FAILED
	)

	if is_success:
		_mark_donation_success(donation, cf_payment_id)
	elif is_failed:
		if donation.status != "Success":
			donation.db_set("status", "Failed", update_modified=True)
	elif donation.status == "Initiated":
		donation.db_set("status", "Pending", update_modified=True)


def _mark_donation_success(donation, cf_payment_id: str | None = None):
	if donation.status == "Success" and donation.payment_entry:
		return

	updates = {"status": "Success"}
	if cf_payment_id:
		updates["cf_payment_id"] = cf_payment_id
	donation.db_set(updates, update_modified=True)
	donation.reload()

	try:
		create_payment_entry_for_donation(donation.name)
	except Exception:
		frappe.log_error(frappe.get_traceback(), f"Payment Entry failed for {donation.name}")

	_send_donor_acknowledgement(donation.name)


def _sync_donation_from_order(donation):
	order = cashfree_client.get_order(donation.cashfree_order_id)
	status = (order.get("order_status") or "").upper()
	if status in ORDER_STATUS_PAID:
		_mark_donation_success(donation)
	elif status in ORDER_STATUS_FAILED:
		if donation.status != "Success":
			donation.db_set("status", "Failed", update_modified=True)
	elif donation.status == "Initiated":
		donation.db_set("status", "Pending", update_modified=True)


def _send_donor_acknowledgement(donation_name: str):
	"""Optional free email via Frappe if Email Account is configured."""
	try:
		donation = frappe.get_doc("Donation", donation_name)
		if not donation.email:
			return
		settings = frappe.get_single("Cashfree Settings")
		org = settings.org_display_name or "Sevamrita Foundation"
		subject = f"Donation acknowledgement — {donation.name}"
		message = f"""
			<p>Dear {frappe.utils.escape_html(donation.full_name)},</p>
			<p>Thank you for donating <b>₹{flt(donation.amount):,.2f}</b> to {frappe.utils.escape_html(org)}.</p>
			<p>Receipt ID: <b>{donation.name}</b></p>
			{"<p>You requested an 80G acknowledgement. Formal Form 10BE is issued after annual Form 10BD filing.</p>" if donation.want_80g else ""}
			<p>With gratitude,<br>{frappe.utils.escape_html(org)}</p>
		"""
		frappe.sendmail(
			recipients=[donation.email],
			subject=subject,
			message=message,
			delayed=True,
			retry=1,
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "Donor acknowledgement email failed")


def mark_donation_from_order_status(donation_name: str):
	"""Used by reconcile job."""
	donation = frappe.get_doc("Donation", donation_name)
	if not donation.cashfree_order_id:
		return donation.status
	_sync_donation_from_order(donation)
	donation.reload()
	return donation.status
