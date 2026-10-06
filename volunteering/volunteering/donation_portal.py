"""Accounts Manager Home workflow for manually received donations.

Cashfree donations remain on their existing path. A staff-recorded donation is
posted exactly once with a balanced Journal Entry. General donations get a private
acknowledgement receipt; CSR donations do not issue one.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from decimal import Decimal, InvalidOperation

import frappe
from frappe import _
from frappe.model.naming import getseries
from frappe.utils import cstr, formatdate, getdate, money_in_words, nowdate
from frappe.utils.password import decrypt, encrypt
from markupsafe import escape

from volunteering.volunteering.chart_of_accounts_portal import SEVAMRITA_COMPANY
from volunteering.volunteering.invoice_generator import _signature_png
from volunteering.volunteering.doctype.donation.donation import manual_donation_write

DONOR_DOCTYPE = "Donation Donor"
SIGNATORY_DOCTYPE = "Donation Receipt Signatory"
SETTINGS_DOCTYPE = "Donation Receipt Settings"
DONATION_TYPES = {"General", "CSR"}
DONATION_CREDIT_LABELS = {"General": "General Donations", "CSR": "CSR Grants"}
PAYMENT_METHODS = {"Cash", "Cheque", "Online", "Bank Transfer", "UPI"}
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PHONE_RE = re.compile(r"^\+?[0-9\s().-]+$")


def _require_manager():
	user = frappe.session.user
	if user != "Administrator" and (user == "Guest" or "Accounts Manager" not in frappe.get_roles(user)):
		frappe.throw(_("Only Accounts Managers and Administrator can register donations."), frappe.PermissionError)


def _clean(value, label, length=200, required=False):
	value = " ".join(cstr(value).strip().split())
	if required and not value:
		frappe.throw(_("{0} is required.").format(label))
	if len(value) > length:
		frappe.throw(_("{0} is too long.").format(label))
	return value


def _phone(value, *, required=False):
	value = _clean(value, "Donor phone number", 40, required)
	if value and (not PHONE_RE.fullmatch(value) or not 7 <= sum(char.isdigit() for char in value) <= 15):
		frappe.throw(_("Enter a valid donor phone number."))
	return value


def _details(raw):
	raw = frappe.parse_json(raw)
	if not isinstance(raw, dict):
		frappe.throw(_("Enter valid donation details."))
	return raw


def _settings():
	return frappe.get_single(SETTINGS_DOCTYPE)


def _donor_payload(row):
	return {key: row.get(key) or "" for key in (
		"name", "donor_name", "donor_type", "address", "pan", "mobile_number", "email"
	)}


def _account_rows():
	rows = frappe.get_all(
		"Account",
		filters={"company": SEVAMRITA_COMPANY, "is_group": 0, "disabled": 0},
		fields=["name", "account_name", "root_type", "account_type", "account_currency"],
		order_by="root_type asc, account_name asc",
		limit_page_length=0,
	)
	return {
		"received_into": [row for row in rows if row.root_type == "Asset" and row.account_type in ("Bank", "Cash")],
		"donation_credit_by_type": {
			donation_type: next(
				(row for row in rows if row.root_type == "Income" and row.account_name == label),
				None,
			)
			for donation_type, label in DONATION_CREDIT_LABELS.items()
		},
	}


@frappe.whitelist(methods=["POST"])
def get_donation_workspace():
	_require_manager()
	settings = _settings()
	return {
		"company": SEVAMRITA_COMPANY,
		"today": nowdate(),
		"donors": [_donor_payload(row) for row in frappe.get_all(
			DONOR_DOCTYPE,
			fields=["name", "donor_name", "donor_type", "address", "pan", "mobile_number", "email"],
			order_by="donor_name asc", limit_page_length=0,
		)],
		"signatories": frappe.get_all(
			SIGNATORY_DOCTYPE, filters={"disabled": 0},
			fields=["name", "signatory_name", "designation"], order_by="signatory_name asc", limit_page_length=0,
		),
		"accounts": _account_rows(),
		"settings": {key: settings.get(key) or "" for key in (
			"organisation_name", "registered_address", "contact_email", "cin",
			"organisation_pan", "eighty_g_number", "eighty_g_valid_until"
		)},
		"history": frappe.get_all(
			"Donation", filters={"source": ["in", ["Office-cash", "Office-online"]]},
			fields=["name", "full_name", "amount", "received_on", "donation_purpose", "receipt_number", "receipt_file", "journal_entry"],
			order_by="creation desc", limit_page_length=100,
		),
	}


@frappe.whitelist(methods=["POST"])
def save_donation_receipt_settings(details):
	_require_manager()
	raw = _details(details)
	settings = _settings()
	for key, label, limit in (
		("organisation_name", "Organisation name", 160),
		("registered_address", "Registered office address", 600),
		("contact_email", "Contact email", 140),
		("cin", "CIN", 40),
		("organisation_pan", "Organisation PAN", 10),
		("eighty_g_number", "80G registration number", 80),
	):
		value = _clean(raw.get(key), label, limit, key in {"organisation_name", "registered_address", "contact_email"})
		if key == "organisation_pan":
			value = value.upper()
			if value and not PAN_RE.fullmatch(value):
				frappe.throw(_("Enter a valid organisation PAN."))
		settings.set(key, value)
	valid_until = raw.get("eighty_g_valid_until") or None
	if valid_until:
		getdate(valid_until)
	settings.eighty_g_valid_until = valid_until
	settings.save(ignore_permissions=True)
	return get_donation_workspace()


@frappe.whitelist(methods=["POST"])
def save_donation_signatory(name, designation, signature_data):
	_require_manager()
	name = _clean(name, "Authorised signatory name", 140, True)
	designation = _clean(designation, "Designation", 140)
	_signature_png(signature_data)
	if frappe.db.exists(SIGNATORY_DOCTYPE, name):
		doc = frappe.get_doc(SIGNATORY_DOCTYPE, name)
	else:
		doc = frappe.new_doc(SIGNATORY_DOCTYPE)
		doc.signatory_name = name
	doc.designation = designation
	doc.signature_data = signature_data
	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
	return get_donation_workspace()


@frappe.whitelist(methods=["POST"])
def update_donation_donor(donor, details):
	"""Correct a saved donor for future receipts; issued receipts stay frozen."""
	_require_manager()
	raw = _details(details)
	if not frappe.db.exists(DONOR_DOCTYPE, donor):
		frappe.throw(_("Select a saved donor first."))
	doc = frappe.get_doc(DONOR_DOCTYPE, donor)
	name = _clean(raw.get("donor_name"), "Donor name", 160, True)
	address = _clean(raw.get("address"), "Donor address", 600, True)
	pan = _clean(raw.get("pan"), "Donor PAN", 10).upper()
	if pan and not PAN_RE.fullmatch(pan):
		frappe.throw(_("Enter a valid donor PAN."))
	duplicate = frappe.db.get_value(DONOR_DOCTYPE, {"pan": pan}, "name") if pan else None
	if duplicate and duplicate != doc.name:
		frappe.throw(_("This PAN belongs to another saved donor."))
	donor_type = raw.get("donor_type") or "Individual"
	if donor_type not in {"Individual", "Organisation"}:
		frappe.throw(_("Choose Individual or Organisation."))
	doc.update({
		"donor_name": name, "donor_type": donor_type, "address": address, "pan": pan,
		"mobile_number": _phone(raw.get("mobile_number")),
		"email": _clean(raw.get("email"), "Email", 140),
	})
	doc.save(ignore_permissions=True)
	return get_donation_workspace()


def _require_donor_details(doc, donation_type):
	_clean(doc.donor_name, "Donor name", 160, True)
	_clean(doc.address, "Donor address", 600, True)
	pan = _clean(doc.pan, "Donor PAN", 10, True).upper()
	if not PAN_RE.fullmatch(pan):
		frappe.throw(_("Enter a valid donor PAN."))
	if donation_type == "General":
		_phone(doc.mobile_number, required=True)
	else:
		_phone(doc.mobile_number)
	if donation_type == "CSR" and doc.donor_type != "Organisation":
		frappe.throw(_("A CSR donor must be an organisation."))


def _resolve_donor(raw, donation_type):
	donor_id = _clean(raw.get("donor"), "Donor ID", 140)
	if donor_id:
		if not frappe.db.exists(DONOR_DOCTYPE, donor_id):
			frappe.throw(_("Choose a donor from the suggestions, or enter a new donor."))
		doc = frappe.get_doc(DONOR_DOCTYPE, donor_id)
		for field in ("donor_name", "donor_type", "address", "pan", "mobile_number", "email"):
			if field in raw and cstr(raw[field] or "").strip() != cstr(doc.get(field) or "").strip():
				frappe.throw(_("Save the changed donor details before recording this donation."))
		_require_donor_details(doc, donation_type)
		return doc
	name = _clean(raw.get("donor_name"), "Donor name", 160, True)
	address = _clean(raw.get("address"), "Donor address", 600, True)
	pan = _clean(raw.get("pan"), "Donor PAN", 10, True).upper()
	if not PAN_RE.fullmatch(pan):
		frappe.throw(_("Enter a valid donor PAN."))
	if pan and frappe.db.exists(DONOR_DOCTYPE, {"pan": pan}):
		frappe.throw(_("This PAN belongs to a saved donor. Select that donor instead."))
	donor_type = raw.get("donor_type") or ("Organisation" if donation_type == "CSR" else "Individual")
	if donor_type not in {"Individual", "Organisation"}:
		frappe.throw(_("Choose Individual or Organisation."))
	if donation_type == "CSR" and donor_type != "Organisation":
		frappe.throw(_("A CSR donor must be an organisation."))
	doc = frappe.get_doc({
		"doctype": DONOR_DOCTYPE,
		"donor_name": name,
		"donor_type": donor_type,
		"address": address,
		"pan": pan,
		"mobile_number": _phone(raw.get("mobile_number"), required=donation_type == "General"),
		"email": _clean(raw.get("email"), "Email", 140),
	})
	_require_donor_details(doc, donation_type)
	doc.insert(ignore_permissions=True)
	return doc


def _validate_account(name, *, use):
	row = frappe.db.get_value(
		"Account", name,
		["company", "is_group", "disabled", "root_type", "account_type", "account_currency"],
		as_dict=True,
	)
	if not row or row.company != SEVAMRITA_COMPANY or row.is_group or row.disabled:
		frappe.throw(_("Choose an active Sevamrita ledger account for {0}.").format(use))
	if row.account_currency not in (None, "", "INR"):
		frappe.throw(_("This Home form currently supports INR accounts only."))
	if use == "receipt" and (row.root_type != "Asset" or row.account_type not in ("Cash", "Bank")):
		frappe.throw(_("Money must be received into a Cash or Bank account."))
	if use == "credit" and row.root_type not in ("Income", "Equity"):
		frappe.throw(_("Choose an Income or Equity credit account for the donation."))
	return row


def _donation_credit_account(donation_type):
	label = DONATION_CREDIT_LABELS[donation_type]
	accounts = frappe.get_all(
		"Account",
		filters={
			"company": SEVAMRITA_COMPANY,
			"account_name": label,
			"root_type": "Income",
			"is_group": 0,
			"disabled": 0,
		},
		pluck="name",
		limit=2,
	)
	if len(accounts) != 1:
		frappe.throw(
			_("Exactly one active Income ledger named {0} is required for {1} donations.").format(
				label, donation_type
			)
		)
	return accounts[0]


def _amount(value):
	try:
		amount = Decimal(str(value)).quantize(Decimal("0.01"))
	except (InvalidOperation, TypeError, ValueError):
		frappe.throw(_("Enter a valid donation amount."))
	if amount <= 0 or amount > Decimal("999999999999.99"):
		frappe.throw(_("Donation amount must be positive and within the supported range."))
	return amount


def _donor_signature_fingerprint(raw):
	return hashlib.sha256(json.dumps(
		{key: value for key, value in raw.items() if key not in {"donor_signature_data", "donor_signature_proof"}},
		sort_keys=True, default=str, separators=(",", ":"),
	).encode()).hexdigest()


@frappe.whitelist(methods=["POST"])
def bind_donation_donor_signature(details):
	"""Bind a donor's on-screen signature to the donation details they saw."""
	_require_manager()
	raw = _details(details)
	signature = _signature_png(raw.get("donor_signature_data"))
	if not signature:
		frappe.throw(_("Draw the donor signature first."))
	return {"proof": encrypt(json.dumps({
		"purpose": "donation-donor-signature-v1",
		"user": frappe.session.user,
		"details": _donor_signature_fingerprint(raw),
		"signature": hashlib.sha256(signature).hexdigest(),
	}))}


def _validate_donor_signature_proof(raw):
	try:
		proof = json.loads(decrypt(raw.get("donor_signature_proof") or ""))
	except (frappe.ValidationError, ValueError, TypeError):
		frappe.throw(_("Ask the donor to sign again before issuing this receipt."))
	if not isinstance(proof, dict):
		frappe.throw(_("Ask the donor to sign again before issuing this receipt."))
	signature = _signature_png(raw.get("donor_signature_data"))
	if (
		proof.get("purpose") != "donation-donor-signature-v1"
		or proof.get("user") != frappe.session.user
		or proof.get("details") != _donor_signature_fingerprint(raw)
		or proof.get("signature") != hashlib.sha256(signature).hexdigest()
	):
		frappe.throw(_("Donation details changed after the donor signed. Ask them to sign again."))


def _receipt_pdf(donation, settings, signatory):
	from frappe.utils.pdf import get_pdf

	h = lambda value: str(escape(cstr(value or "")))
	with open(frappe.get_app_path("volunteering", "public", "images", "sevamrita-donation-logo.png"), "rb") as handle:
		logo = base64.b64encode(handle.read()).decode("ascii")
	signature = _signature_png(signatory.signature_data)
	donor_signature = _signature_png(donation.donor_signature_data) if donation.donor_signature_data else b""
	org_signature = base64.b64encode(signature).decode("ascii")
	donor_image = (
		f'<img class="sign" src="data:image/png;base64,{base64.b64encode(donor_signature).decode("ascii")}">'
		if donor_signature else ""
	)
	registration = ""
	if donation.want_80g:
		registration = f'<p><b>80G registration:</b> {h(settings.eighty_g_number)} (valid until {h(formatdate(settings.eighty_g_valid_until))})</p>'
	contact = " | ".join(filter(None, [h(settings.contact_email), f"CIN: {h(settings.cin)}" if settings.cin else "", f"PAN: {h(settings.organisation_pan)}" if settings.organisation_pan else ""]))
	html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
	@page {{ size:A4; margin:13mm; }} body {{ font-family:Arial,sans-serif; font-size:10pt; color:#17322e; line-height:1.45; }}
	h1,h2,p {{ margin:0 0 3mm; }} h1 {{ text-align:center; font-size:17pt; }} h2 {{ text-align:center; font-size:14pt; margin-top:7mm; }}
	.header {{ text-align:center; border-bottom:2px solid #267a76; padding-bottom:4mm; min-height:26mm; }} .header img {{ float:left; width:25mm; height:25mm; object-fit:contain; margin:0 2mm 0 0; }} .muted {{ color:#53645f; }}
	table {{ width:100%; border-collapse:collapse; margin-top:4mm; }} td {{ border:1px solid #8ab9c1; padding:3mm; vertical-align:top; }}
	.label {{ display:block; font-size:8pt; color:#53645f; }} .amount {{ background:#e0f1f2; font-size:13pt; font-weight:bold; }}
	.signatures {{ display:table; width:100%; margin-top:9mm; }} .signature-cell {{ display:table-cell; width:50%; vertical-align:bottom; height:28mm; }}
	.sign {{ max-width:55mm; max-height:20mm; display:block; }} .terms {{ border-top:1px solid #8ab9c1; margin-top:8mm; padding-top:4mm; font-size:8.5pt; }}
	</style></head><body><div class="header"><img src="data:image/png;base64,{logo}" alt="Sevamrita Foundation"><h1>{h(settings.organisation_name)}</h1><p>{h(settings.registered_address)}</p><p class="muted">{contact}</p></div>
	<h2>DONATION RECEIPT</h2><p class="muted" style="text-align:center">Acknowledgement of a donation received; not the statutory donation certificate</p>
	<table><tr><td><span class="label">Receipt number</span>{h(donation.receipt_number)}</td><td><span class="label">Date issued</span>{h(formatdate(donation.receipt_date))}</td></tr>
	<tr><td><span class="label">Donation amount</span><span class="amount">₹ {h(f'{Decimal(str(donation.amount)):,.2f}')}</span></td><td><span class="label">Amount in words</span>{h(money_in_words(donation.amount, 'INR'))}</td></tr>
	<tr><td><span class="label">Donor</span>{h(donation.full_name)}<br>{h(donation.address)}</td><td><span class="label">Date received</span>{h(formatdate(donation.received_on))}<br><span class="label">Purpose</span>{h(donation.donation_purpose)}</td></tr>
	<tr><td><span class="label">Donor PAN</span>{h(donation.pan) or 'Not provided'}<br><span class="label">Mobile / WhatsApp</span>{h(donation.mobile_number) or 'Not provided'}<br><span class="label">Email</span>{h(donation.email) or 'Not provided'}</td>
	<td><span class="label">Payment method</span>{h(donation.payment_method)}<br><span class="label">Cheque / transaction reference</span>{h(donation.payment_reference) or 'Not applicable'}</td></tr></table>
	<div class="signatures"><div class="signature-cell">{donor_image}{'Donor signature (cash payment)' if donor_image else ''}</div>
	<div class="signature-cell"><img class="sign" src="data:image/png;base64,{org_signature}"><b>{h(signatory.signatory_name)}</b><br>{h(signatory.designation)}<br>Authorised representative</div></div>
	<div class="terms">{registration}<p>Please report any error in your name, address, PAN or contact details to {h(settings.contact_email)}.</p>
	<p>This receipt only acknowledges the donation. Any statutory donation certificate is issued separately, where applicable. A cash donation exceeding ₹2,000 is not eligible for deduction under section 80G.</p></div>
	<p style="text-align:center;margin-top:9mm">Thank you for your generous support.</p></body></html>"""
	try:
		return get_pdf(html, options={"page-size": "A4", "encoding": "UTF-8"})
	except OSError as error:
		if "wkhtmltopdf" not in str(error).lower():
			raise
		from weasyprint import HTML
		return HTML(string=html).write_pdf()


@frappe.whitelist(methods=["POST"])
def register_donation(details):
	"""Post a donation once; issue a private receipt only for General donations."""
	_require_manager()
	raw = _details(details)
	key = _clean(raw.get("request_key"), "Request key", 100, True)
	existing = frappe.db.get_value("Donation", {"registration_key": key}, "name")
	if existing:
		return _registered_result(existing)
	amount = _amount(raw.get("amount"))
	method = raw.get("payment_method")
	if method not in PAYMENT_METHODS:
		frappe.throw(_("Choose a payment method."))
	purpose = raw.get("donation_purpose")
	if purpose not in DONATION_TYPES:
		frappe.throw(_("Choose General donation or CSR donation first."))
	if not raw.get("received_on"):
		frappe.throw(_("Date received is required."))
	received_on = getdate(raw.get("received_on"))
	if received_on > getdate(nowdate()):
		frappe.throw(_("The received date cannot be in the future."))
	reference = _clean(raw.get("payment_reference"), "Payment reference", 140)
	if method != "Cash" and not reference:
		frappe.throw(_("Enter the cheque or transaction reference."))
	if method == "Cheque" and not raw.get("cheque_cleared"):
		frappe.throw(_("Only register a cheque donation after it has cleared."))
	debit_account = _clean(raw.get("received_into_account"), "Received into account", 140, True)
	credit_account = _donation_credit_account(purpose)
	provided_credit = _clean(raw.get("donation_account"), "Donation account", 140)
	if provided_credit and provided_credit != credit_account:
		frappe.throw(_("The donation type determines its credit ledger; it cannot be changed on this form."))
	debit_row = _validate_account(debit_account, use="receipt")
	_validate_account(credit_account, use="credit")
	if method == "Cash" and debit_row.account_type != "Cash":
		frappe.throw(_("Cash donations must be recorded in a Cash ledger."))
	if method != "Cash" and debit_row.account_type != "Bank":
		frappe.throw(_("Non-cash donations must be recorded in a Bank ledger."))
	signatory = None
	settings = None
	donor_signature = ""
	want_80g = False
	receipt_number = None
	if purpose == "General":
		signatory_name = _clean(raw.get("receipt_signatory"), "Authorised signatory", 140, True)
		signatory = frappe.get_doc(SIGNATORY_DOCTYPE, signatory_name)
		if signatory.disabled:
			frappe.throw(_("Choose an active authorised signatory."))
		donor_signature = raw.get("donor_signature_data") or ""
		if method == "Cash" and not donor_signature:
			frappe.throw(_("Ask the cash donor to sign on screen."))
		if donor_signature:
			_signature_png(donor_signature)
		settings = _settings()
		for field, label in (("organisation_name", "Organisation name"), ("registered_address", "Registered office address"), ("contact_email", "Contact email")):
			if not settings.get(field):
				frappe.throw(_("Set {0} in Receipt Settings before issuing receipts.").format(label))
		want_80g = bool(raw.get("want_80g"))
		if want_80g:
			if method == "Cash" and amount > 2000:
				frappe.throw(_("A cash donation over ₹2,000 cannot be marked for 80G deduction."))
			if not settings.eighty_g_number or not settings.eighty_g_valid_until or getdate(settings.eighty_g_valid_until) < received_on:
				frappe.throw(_("Configure a valid 80G registration covering the donation date first."))
		if donor_signature:
			_validate_donor_signature_proof(raw)
	else:
		if (
			raw.get("receipt_signatory")
			or raw.get("donor_signature_data")
			or raw.get("donor_signature_proof")
			or raw.get("want_80g")
		):
			frappe.throw(_("CSR donations do not issue a signed receipt or 80G acknowledgement here."))
	donor = _resolve_donor(raw, purpose)
	if purpose == "General":
		# Receipt numbers are assigned at issue time, independent of the donation date.
		year = getdate(nowdate()).year
		receipt_number = f"RE-{year}-{getseries(f'RE-{year}-', 5)}"
	donation = frappe.get_doc({
		"doctype": "Donation", "full_name": donor.donor_name,
		"mobile_number": donor.mobile_number or "", "email": donor.email or "",
		"address": donor.address, "pan": donor.pan or "", "donor": donor.name,
		"donor_type": donor.donor_type, "amount": float(amount), "currency": "INR",
		"status": "Success", "source": "Office-cash" if method == "Cash" else "Office-online",
		"want_80g": int(want_80g), "received_on": received_on,
		"donation_purpose": purpose, "payment_method": method,
		"payment_reference": reference, "received_into_account": debit_account,
		"donation_account": credit_account, "receipt_number": receipt_number,
		"receipt_date": nowdate() if signatory else None,
		"receipt_signatory": signatory.name if signatory else None,
		"donor_signature_data": donor_signature, "registration_key": key,
	})
	with manual_donation_write():
		donation.insert(ignore_permissions=True)
	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = SEVAMRITA_COMPANY
	je.posting_date = received_on
	je.user_remark = f"{purpose} donation {donation.name}" + (f" / receipt {receipt_number}" if receipt_number else "") + f" — {donor.donor_name}"
	je.append("accounts", {"account": debit_account, "debit_in_account_currency": float(amount)})
	je.append("accounts", {"account": credit_account, "credit_in_account_currency": float(amount)})
	je.insert(ignore_permissions=True)
	je.submit()
	donation.db_set("journal_entry", je.name, update_modified=False)
	if purpose == "General":
		from frappe.utils.file_manager import save_file

		pdf = _receipt_pdf(donation, settings, signatory)
		file = save_file(f"donation-receipt-{receipt_number}.pdf", pdf, "Donation", donation.name, is_private=1)
		donation.db_set("receipt_file", file.file_url, update_modified=False)
	return _registered_result(donation.name)


def _registered_result(name):
	row = frappe.db.get_value(
		"Donation", name, ["name", "donation_purpose", "receipt_number", "receipt_file", "journal_entry"], as_dict=True
	)
	return dict(row)
