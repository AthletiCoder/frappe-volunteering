# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee-facing GST and non-GST invoice document generator.

This module deliberately does not create an ERP accounting document. It returns
an in-memory PDF and DOCX for supplier signature or the employee's own volunteer
expense confirmation before attaching the signed document to an Expense Claim.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO

import frappe
from frappe import _
from frappe.model.naming import getseries
from frappe.utils import formatdate, getdate, money_in_words, nowdate
from frappe.utils.password import decrypt, encrypt
from markupsafe import escape

from volunteering.volunteering.authority import get_employee_for_user

MAX_ITEMS = 20
MONEY_PLACES = Decimal("0.01")
MAX_MONEY = Decimal("999999999999.99")
MAX_QUANTITY = Decimal("999999999")
ALLOWED_TYPES = {"GST", "NON_GST"}
ALLOWED_SIGNERS = {"SUPPLIER", "VOLUNTEER"}
ALLOWED_TAX_MODES = {"CGST_SGST", "IGST"}
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


@frappe.whitelist(methods=["POST"])
def get_invoice_generator_defaults():
	employee = _require_employee()
	from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details

	company = frappe.db.get_value("Employee", employee, "company")
	company_doc = frappe.get_cached_doc("Company", company)
	address_choices = _company_address_choices(company, company_doc)
	default_choice = next(
		(choice for choice in address_choices if choice["is_primary_address"]),
		address_choices[0] if address_choices else None,
	)
	address = default_choice["party"] if default_choice else _company_party(company_doc, {})
	approved_bank = get_approved_bank_details(employee, reveal=False)
	return {
		"employee": employee,
		"volunteer": _employee_signer(employee),
		"company": company,
		"invoice_date": nowdate(),
		"remittance_bank": approved_bank,
		"has_approved_bank": bool(approved_bank),
		"office_addresses": address_choices,
		"default_office_address": default_choice["name"] if default_choice else "",
		"consignee": address,
	}


@frappe.whitelist(methods=["POST"])
def generate_invoice_documents(payload, output_format="both", generation_reference=None):
	"""Validate invoice data and return private, in-memory PDF and DOCX downloads."""
	# MariaDB snapshot isolation may reject a counter updated by an overlapping
	# request even after a row lock. Restart the whole generation transaction and
	# re-check employee/bank approval rather than retrying with a stale snapshot.
	for attempt in range(3):
		try:
			return _generate_invoice_documents(payload, output_format, generation_reference)
		except frappe.QueryDeadlockError:
			frappe.db.rollback()
			if attempt == 2:
				frappe.throw(
					_("Invoice generation is busy. Please try again; no invoice number was consumed.")
				)


def _generate_invoice_documents(payload, output_format="both", generation_reference=None):
	if output_format not in {"pdf", "docx", "both"}:
		frappe.throw(_("Choose PDF or Word document."))
	employee = _require_employee()
	from volunteering.volunteering.employee_bank_accounts import get_approved_bank_details

	approved_bank = get_approved_bank_details(employee, reveal=True)
	if not approved_bank:
		frappe.throw(
			_(
				"An Accounts Manager must approve your reimbursement bank account before you can generate an invoice."
			)
		)
	# Validate first, without trusting or allocating a browser-supplied number.
	data = _normalise_payload(
		_apply_selected_office_addresses(payload, employee),
		bank_override=approved_bank,
		invoice_number_override="INV-AUTOMATIC",
		volunteer_override=_employee_signer(employee),
	)
	fingerprint = hashlib.sha256(
		json.dumps(data, sort_keys=True, default=str, separators=(",", ":")).encode()
	).hexdigest()
	data["invoice_number"] = _number_for_generation(employee, fingerprint, generation_reference)
	stem = _safe_filename(data["invoice_number"])
	result = {
		"invoice_number": data["invoice_number"],
		"grand_total": float(data["grand_total"]),
		"amount_in_words": data["amount_in_words"],
		"signer_type": data["signer_type"],
		"notice": data["notice"],
	}
	if output_format in {"pdf", "both"}:
		result["pdf"] = _download(f"{stem}.pdf", "application/pdf", _build_pdf(data))
	if output_format in {"docx", "both"}:
		result["docx"] = _download(
			f"{stem}.docx",
			"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
			_build_docx(data),
		)
	# An authenticated, opaque reference permits the other format for exactly
	# this employee and content, without trusting client-supplied invoice numbers.
	# Issue it only after the requested document(s) succeed.
	result["generation_reference"] = encrypt(
		json.dumps(
			{
				"purpose": "invoice-generator-v1",
				"employee": employee,
				"fingerprint": fingerprint,
				"invoice_number": data["invoice_number"],
			}
		)
	)
	return result


def _number_for_generation(employee, fingerprint, reference):
	if reference:
		try:
			identity = json.loads(decrypt(reference))
		except ValueError, TypeError, frappe.ValidationError:
			frappe.throw(_("Invalid invoice generation reference. Generate again."))
		if not isinstance(identity, dict) or identity.get("purpose") != "invoice-generator-v1":
			frappe.throw(_("Invalid invoice generation reference. Generate again."))
		if identity.get("employee") != employee:
			frappe.throw(_("This invoice belongs to another employee."), frappe.PermissionError)
		if identity.get("fingerprint") == fingerprint:
			return identity["invoice_number"]
	return _next_invoice_number()


def _next_invoice_number():
	"""Allocate one shared annual number inside the generation transaction."""
	year = getdate(nowdate()).year
	key = f"SEVAMRITA-FORM-INVOICE-{year}-"
	series = frappe.qb.DocType("Series")
	if not frappe.qb.from_(series).select(series.name).where(series.name == key).run():
		# The first generation has no Series row to lock. Serialize its creation
		# on an existing site Company row, then let getseries re-read with a lock.
		# Avoid a no-op UPSERT: MariaDB can reject it from a stale snapshot.
		company = frappe.qb.DocType("Company")
		frappe.qb.from_(company).select(company.name).orderby(company.name).limit(1).for_update().run()
	# getseries locks the counter until both documents succeed and the POST
	# commits. Frappe rolls back allocation if document generation fails.
	number = f"INV-{year}-{getseries(key, 6)}"
	if len(number) > 16:
		frappe.throw(_("The annual invoice numbering sequence is exhausted. Contact your administrator."))
	return number


def _require_employee():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in as an employee to prepare an invoice."), frappe.PermissionError)
	employee = get_employee_for_user(user)
	if not employee or frappe.db.get_value("Employee", employee, "status") != "Active":
		frappe.throw(_("Your user must be linked to an active Employee record."), frappe.PermissionError)
	return employee


def _employee_signer(employee):
	# A volunteer signs their own statement. Never trust a browser-supplied
	# employee identity or present the volunteer as a supplier representative.
	return {
		"employee": employee,
		"name": frappe.db.get_value("Employee", employee, "employee_name") or employee,
	}


def _company_address_choices(company, company_doc=None):
	from volunteering.volunteering.office_addresses import invoice_address_choices

	company_doc = company_doc or frappe.get_cached_doc("Company", company)
	choices = invoice_address_choices(company)
	for choice in choices:
		choice["party"] = _company_party(company_doc, choice["party"])
	return choices


def _company_party(company_doc, address):
	return {
		"name": company_doc.company_name or company_doc.name,
		"address": address.get("address", ""),
		"state": address.get("state", ""),
		"pin_code": address.get("pin_code", ""),
		"gstin": (company_doc.get("tax_id") or "").strip().upper(),
	}


def _apply_selected_office_addresses(payload, employee):
	raw = frappe.parse_json(payload) if isinstance(payload, str) else payload
	if not isinstance(raw, dict):
		return raw
	consignee_name = str(raw.get("consignee_address_name") or "").strip()
	buyer_same = bool(raw.get("buyer_same_as_consignee", True))
	buyer_name = str(raw.get("buyer_address_name") or "").strip()
	if not consignee_name and (buyer_same or not buyer_name):
		return raw

	company = frappe.db.get_value("Employee", employee, "company")
	choices = {choice["name"]: choice for choice in _company_address_choices(company)}
	values = dict(raw)
	if consignee_name:
		if consignee_name not in choices:
			frappe.throw(_("Choose a current Sevamrita office address for the consignee."))
		values["consignee"] = choices[consignee_name]["party"]
	if not buyer_same:
		if not buyer_name or buyer_name not in choices:
			frappe.throw(_("Choose a current Sevamrita office address for the buyer."))
		values["buyer"] = choices[buyer_name]["party"]
	return values


def _normalise_payload(payload, bank_override=None, invoice_number_override=None, volunteer_override=None):
	raw = frappe.parse_json(payload) if isinstance(payload, str) else payload
	if not isinstance(raw, dict):
		frappe.throw(_("Invoice details must be a valid object."))

	invoice_type = _required_choice(raw, "invoice_type", ALLOWED_TYPES, _("Invoice type"))
	# Keep supplier signing as the default for older clients without a signer selector.
	signer_type = _required_choice(
		{"signer_type": raw.get("signer_type", "SUPPLIER")},
		"signer_type",
		ALLOWED_SIGNERS,
		_("signer"),
	)
	data = {
		"invoice_type": invoice_type,
		"signer_type": signer_type,
		"copy_label": _("ORIGINAL FOR RECIPIENT"),
		"title": "TAX INVOICE" if invoice_type == "GST" else "INVOICE",
		"invoice_number": invoice_number_override
		if invoice_number_override is not None
		else _required_text(raw, "invoice_number", _("Invoice number"), 80),
		"invoice_date": _date(raw.get("invoice_date"), _("Invoice date")),
		"buyer_order_number": _text(raw.get("buyer_order_number"), 100),
		"buyer_order_date": _optional_date(raw.get("buyer_order_date")),
		"supplier_reference": _text(raw.get("supplier_reference"), 140),
		"dispatch_document_number": _text(raw.get("dispatch_document_number"), 100),
		"delivery_note_date": _optional_date(raw.get("delivery_note_date")),
		"supplier": _party(raw.get("supplier"), _("Supplier")),
		"consignee": _party(raw.get("consignee"), _("Consignee")),
		"buyer_same_as_consignee": bool(raw.get("buyer_same_as_consignee", True)),
		"transportation_charges": _money(raw.get("transportation_charges"), _("Transportation charges")),
		"other_charges": _money(raw.get("other_charges"), _("Other charges")),
		# The public endpoint always supplies an approved server-side override. Keeping
		# the fallback makes the pure rendering helpers independently testable.
		"bank": _bank(bank_override if bank_override is not None else raw.get("bank")),
		"authorised_signatory": _text(raw.get("authorised_signatory"), 120)
		if signer_type == "SUPPLIER"
		else "",
	}
	data["buyer"] = (
		data["consignee"] if data["buyer_same_as_consignee"] else _party(raw.get("buyer"), _("Buyer"))
	)

	if invoice_type == "GST":
		_validate_gstin(data["supplier"].get("gstin"), _("Supplier GSTIN"), required=True)
		_validate_gstin(data["consignee"].get("gstin"), _("Consignee GSTIN"), required=False)
		if len(data["invoice_number"]) > 16:
			frappe.throw(_("A GST invoice number cannot exceed 16 characters."))
		# The supplied Tax Invoice template has one GST amount row, not separate
		# tax-mode/rate/place-of-supply fields. Accept the amount shown on the bill.
		if "gst_amount" in raw:
			data["gst_amount"] = _money(raw.get("gst_amount"), _("GST amount"))
		else:
			# Compatibility for saved/older clients while the home form migrates.
			legacy_rate = _rate(raw.get("gst_rate"))
			data["gst_amount"] = None
		data["tax_mode"] = _text(raw.get("tax_mode"), 20)
		data["gst_rate"] = _rate(raw.get("gst_rate")) if raw.get("gst_rate") is not None else Decimal("0")
	else:
		_validate_pan(data["supplier"].get("pan"))
		data["tax_mode"] = ""
		data["gst_rate"] = Decimal("0")
		data["gst_amount"] = Decimal("0")

	items = raw.get("items")
	if not isinstance(items, list) or not items:
		frappe.throw(_("Add at least one invoice item."))
	if len(items) > MAX_ITEMS:
		frappe.throw(_("An invoice can contain at most {0} items.").format(MAX_ITEMS))

	data["items"] = []
	for index, raw_item in enumerate(items, start=1):
		if not isinstance(raw_item, dict):
			frappe.throw(_("Invoice item {0} is invalid.").format(index))
		quantity = _positive_decimal(raw_item.get("quantity"), _("Quantity in row {0}").format(index), 3)
		rate = _money(raw_item.get("rate"), _("Rate in row {0}").format(index))
		if rate <= 0:
			frappe.throw(_("Rate in row {0} must be greater than zero.").format(index))
		line_amount = quantity * rate
		if line_amount > MAX_MONEY:
			frappe.throw(_("Amount in row {0} is too large.").format(index))
		data["items"].append(
			{
				"number": index,
				"description": _required_text(
					raw_item, "description", _("Description in row {0}").format(index), 300
				),
				"hsn_sac": _text(raw_item.get("hsn_sac"), 30),
				"unit": _required_text(raw_item, "unit", _("Unit in row {0}").format(index), 20),
				"quantity": quantity,
				"rate": rate,
				"amount": _quantise(line_amount),
			}
		)

	data["items_total"] = _quantise(sum((item["amount"] for item in data["items"]), Decimal("0")))
	taxable_total = data["items_total"] + data["transportation_charges"] + data["other_charges"]
	if taxable_total > MAX_MONEY:
		frappe.throw(_("Invoice total is too large."))
	data["taxable_total"] = _quantise(taxable_total)
	if data["gst_amount"] is None:
		data["gst_amount"] = _quantise(data["taxable_total"] * legacy_rate / Decimal("100"))
	else:
		data["gst_amount"] = _quantise(data["gst_amount"])
	data["cgst_amount"] = Decimal("0")
	data["sgst_amount"] = Decimal("0")
	data["igst_amount"] = Decimal("0")
	if data["tax_mode"] == "CGST_SGST":
		data["cgst_amount"] = _quantise(data["gst_amount"] / Decimal("2"))
		data["sgst_amount"] = data["gst_amount"] - data["cgst_amount"]
	elif data["tax_mode"] == "IGST":
		data["igst_amount"] = data["gst_amount"]
	grand_total = data["taxable_total"] + data["gst_amount"]
	if grand_total > MAX_MONEY:
		frappe.throw(_("Invoice total is too large."))
	data["grand_total"] = _quantise(grand_total)
	data["amount_in_words"] = money_in_words(data["grand_total"], "INR")
	data["declaration_title"] = ""
	data["declaration"] = ""
	data["signature_employee"] = ""
	if signer_type == "VOLUNTEER":
		volunteer = volunteer_override if volunteer_override is not None else raw.get("volunteer")
		volunteer = volunteer if isinstance(volunteer, dict) else {}
		data["signatory_name"] = _required_text(volunteer, "name", _("Volunteer name"), 160)
		data["signature_employee"] = _required_text(volunteer, "employee", _("Volunteer employee"), 140)
		data["signature_context"] = _("Volunteer Signatory")
		data["signature_label"] = _("Signature")
		data["notice"] = ""
	else:
		data["signatory_name"] = data["authorised_signatory"]
		data["signature_context"] = _("For {0}").format(data["supplier"]["name"])
		data["signature_label"] = _("Authorised Signatory")
		if invoice_type == "NON_GST":
			data["declaration_title"] = _("Declaration")
			data["declaration"] = _(
				"I, {0}, proprietor/authorised person of {1}, declare that this business is not registered "
				"under the Goods and Services Tax (GST) Act and therefore does not have a GSTIN."
			).format(data["authorised_signatory"] or _("the undersigned"), data["supplier"]["name"])
		data["notice"] = ""
	return data


def _party(value, label):
	value = value if isinstance(value, dict) else {}
	return {
		"name": _required_text(value, "name", _("{0} name").format(label), 160),
		"address": _required_text(value, "address", _("{0} address").format(label), 600),
		"state": _required_text(value, "state", _("{0} state").format(label), 100),
		"pin_code": _text(value.get("pin_code"), 12),
		"gstin": _text(value.get("gstin"), 15).upper(),
		"pan": _text(value.get("pan"), 10).upper(),
	}


def _bank(value):
	value = value if isinstance(value, dict) else {}
	return {
		"bank_name": _text(value.get("bank_name"), 140),
		"branch": _text(value.get("branch"), 140),
		"account_name": _text(value.get("account_name"), 160),
		"account_number": _text(value.get("account_number"), 50),
		"ifsc": _text(value.get("ifsc"), 20).upper(),
		"swift": _text(value.get("swift"), 20).upper(),
	}


def _required_text(mapping, key, label, max_length):
	value = _text(mapping.get(key), max_length)
	if not value:
		frappe.throw(_("{0} is required.").format(label))
	return value


def _text(value, max_length):
	value = " ".join(str(value or "").strip().split())
	if len(value) > max_length:
		frappe.throw(_("A field exceeds the maximum length of {0} characters.").format(max_length))
	return value


def _required_choice(mapping, key, choices, label):
	value = _text(mapping.get(key), 40).upper()
	if value not in choices:
		frappe.throw(_("Select a valid {0}.").format(label))
	return value


def _date(value, label):
	if not value:
		frappe.throw(_("{0} is required.").format(label))
	try:
		return formatdate(getdate(value), "dd-MM-yyyy")
	except Exception:
		frappe.throw(_("{0} is invalid.").format(label))


def _optional_date(value):
	return _date(value, _("Date")) if value else ""


def _decimal(value, label):
	try:
		amount = Decimal(str(value or 0))
	except InvalidOperation, ValueError:
		frappe.throw(_("{0} must be a number.").format(label))
	if not amount.is_finite():
		frappe.throw(_("{0} must be a finite number.").format(label))
	return amount


def _money(value, label):
	amount = _decimal(value, label)
	if amount < 0:
		frappe.throw(_("{0} cannot be negative.").format(label))
	if amount > MAX_MONEY:
		frappe.throw(_("{0} is too large.").format(label))
	return _quantise(amount)


def _positive_decimal(value, label, places):
	amount = _decimal(value, label)
	if amount <= 0:
		frappe.throw(_("{0} must be greater than zero.").format(label))
	if amount > MAX_QUANTITY:
		frappe.throw(_("{0} is too large.").format(label))
	quantum = Decimal("1").scaleb(-places)
	return amount.quantize(quantum, rounding=ROUND_HALF_UP)


def _rate(value):
	rate = _decimal(value, _("GST rate"))
	if rate < 0 or rate > 100:
		frappe.throw(_("GST rate must be between 0 and 100."))
	return rate.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _quantise(value):
	return Decimal(value).quantize(MONEY_PLACES, rounding=ROUND_HALF_UP)


def _validate_gstin(value, label, required):
	if not value and not required:
		return
	if not value or not GSTIN_PATTERN.fullmatch(value):
		frappe.throw(_("{0} must be a valid 15-character GSTIN.").format(label))


def _validate_pan(value):
	if value and not PAN_PATTERN.fullmatch(value):
		frappe.throw(_("Supplier PAN must be in the format ABCDE1234F."))


def _money_text(value):
	return f"{Decimal(value):,.2f}"


def _quantity_text(value):
	return f"{Decimal(value):f}".rstrip("0").rstrip(".")


def _download(filename, content_type, content):
	return {
		"filename": filename,
		"content_type": content_type,
		"content_base64": base64.b64encode(content).decode("ascii"),
	}


def _safe_filename(invoice_number):
	stem = re.sub(r"[^A-Za-z0-9._-]+", "-", invoice_number).strip("-._")
	return f"invoice-{stem or 'document'}"


def _render_pdf_html(data):
	def h(value):
		return str(escape(str(value or "")))

	items = "".join(
		f"<tr><td>{item['number']}</td><td>{h(item['description'])}</td>"
		f"<td>{h(item['hsn_sac'])}</td><td class='num'>{_quantity_text(item['quantity'])}</td>"
		f"<td class='num'>{_money_text(item['rate'])}</td><td class='num'>{_money_text(item['amount'])}</td></tr>"
		for item in data["items"]
	)
	summary = [
		(_("Total"), data["items_total"]),
	]
	if data["invoice_type"] == "GST":
		summary.append((_("GST"), data["gst_amount"]))
	summary.extend(
		[
			(_("Transportation"), data["transportation_charges"]),
			(_("Others"), data["other_charges"]),
		]
	)
	summary_rows = "".join(
		f"<tr><td colspan='5' class='summary-label'>{h(label)}</td><td class='num'>{_money_text(value)}</td></tr>"
		for label, value in summary
	)
	bank = data["bank"]
	bank_lines = [
		(_("Bank Name"), bank["bank_name"]),
		(_("Branch"), bank["branch"]),
		(_("Account Name"), bank["account_name"]),
		(_("Account No."), bank["account_number"]),
		(_("IFSC Code"), bank["ifsc"]),
		(_("Swift Code"), bank["swift"]),
	]
	bank_html = "<br>".join(f"<b>{h(label)}:</b> {h(value)}" for label, value in bank_lines)
	declaration = (
		f"<div class='declaration'><b>{h(data['declaration_title'])}:</b> {h(data['declaration'])}</div>"
		if data["declaration"]
		else ""
	)
	buyer = data["buyer"]
	return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
@page {{ size: A4; margin: 8mm; }}
body {{ font-family: Arial, sans-serif; color: #111; font-size: 9.5pt; line-height: 1.3; }}
h1 {{ text-align: center; font-size: 17pt; margin: 0 0 3mm; letter-spacing: .5px; }}
.copy {{ text-align: right; font-size: 8pt; margin-bottom: 2mm; }}
table {{ width: 100%; border-collapse: collapse; }}
td, th {{ border: 1px solid #555; padding: 4px 5px; vertical-align: top; }}
th {{ background: #ececec; text-align: center; }}
thead {{ display: table-header-group; }}
tr {{ page-break-inside: avoid; }}
.items {{ table-layout: fixed; }}
.items td {{ overflow-wrap: break-word; }}
.party {{ width: 50%; }}
.label {{ color: #555; font-size: 8pt; text-transform: uppercase; }}
.value {{ font-weight: 600; margin-top: 1px; }}
.num {{ text-align: right; white-space: nowrap; }}
.summary-label {{ text-align: right; font-weight: 600; }}
.grand td {{ font-size: 11pt; font-weight: 700; background: #f2f2f2; }}
.section {{ margin-top: 3mm; }}
.declaration {{ border: 1px solid #555; padding: 5px; margin-top: 3mm; }}
.signature {{ height: 22mm; text-align: right; }}
</style></head><body>
<h1>{h(data["title"])}</h1><div class="copy">{h(data["copy_label"])}</div>
<table><tr><td class="party"><div class="label">{h(_("Supplier Details"))}</div><div class="value">{h(data["supplier"]["name"])}</div>{h(data["supplier"]["address"])}<br>{h(data["supplier"]["state"])} {h(data["supplier"]["pin_code"])}<br>{h(_("GSTIN / UID No.")) if data["invoice_type"] == "GST" else h(_("PAN No."))}: {h(data["supplier"]["gstin"] if data["invoice_type"] == "GST" else data["supplier"]["pan"])}</td>
<td><b>{h(_("Invoice No."))}:</b> {h(data["invoice_number"])}<br><b>{h(_("Invoice Date"))}:</b> {h(data["invoice_date"])}<br><b>{h(_("Buyer's Order No."))}:</b> {h(data["buyer_order_number"])}<br><b>{h(_("Date"))}:</b> {h(data["buyer_order_date"])}<br><b>{h(_("Supplier's Reference"))}:</b> {h(data["supplier_reference"])}<br><b>{h(_("Despatch Document No."))}:</b> {h(data["dispatch_document_number"])}<br><b>{h(_("Delivery Note Date"))}:</b> {h(data["delivery_note_date"])}</td></tr>
<tr><td><div class="label">{h(_("Consignee's Details"))}</div><div class="value">{h(data["consignee"]["name"])}</div>{h(data["consignee"]["address"])}<br>{h(data["consignee"]["state"])} {h(data["consignee"]["pin_code"])}<br>{h(_("GSTIN / UID No."))}: {h(data["consignee"]["gstin"])}</td>
<td><div class="label">{h(_("Buyer's Details (if other than Consignee)"))}</div><div class="value">{h(buyer["name"])}</div>{h(buyer["address"])}<br>{h(buyer["state"])} {h(buyer["pin_code"])}<br>{h(_("GSTIN / UID No."))}: {h(buyer["gstin"])}</td></tr></table>
<table class="section items"><colgroup><col style="width:6%"><col style="width:42%"><col style="width:12%"><col style="width:8%"><col style="width:14%"><col style="width:18%"></colgroup><thead><tr><th>{h(_("Sr. No."))}</th><th>{h(_("Description"))}</th><th>{h(_("HSN / SAC"))}</th><th>{h(_("Qty."))}</th><th>{h(_("Rate"))}</th><th>{h(_("Amount (INR)"))}</th></tr></thead><tbody>{items}{summary_rows}<tr class="grand"><td colspan="5" class="summary-label">{h(_("Grand Total"))}</td><td class="num">{_money_text(data["grand_total"])}</td></tr></tbody></table>
<div class="declaration"><b>{h(_("Amount in words"))}:</b> {h(data["amount_in_words"])}</div>{declaration}
<table class="section"><tr><td class="party"><b>{h(_("Remittance Details"))}</b><br>{bank_html or h(_("Not provided"))}</td><td class="signature"><b>{h(data["signature_context"])}</b><br><br><br>{h(data["signatory_name"])}{f"<br>{h(data['signature_employee'])}" if data["signature_employee"] else ""}<br>{h(data["signature_label"])}</td></tr></table>
</body></html>"""


def _build_pdf(data):
	"""Use Frappe's PDF engine, with a local fallback when wkhtmltopdf is absent."""
	from frappe.utils.pdf import get_pdf

	html = _render_pdf_html(data)
	try:
		return get_pdf(
			html,
			options={
				"page-size": "A4",
				"margin-top": "8mm",
				"margin-right": "8mm",
				"margin-bottom": "10mm",
				"margin-left": "8mm",
				"encoding": "UTF-8",
			},
		)
	except OSError as error:
		if "wkhtmltopdf" not in str(error).lower():
			raise
		try:
			from weasyprint import HTML
		except ImportError:
			frappe.throw(_("PDF generation is unavailable because no supported PDF renderer is installed."))
		return HTML(string=html).write_pdf()


def _build_docx(data):
	from docx import Document
	from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
	from docx.enum.text import WD_ALIGN_PARAGRAPH
	from docx.oxml import OxmlElement
	from docx.shared import Mm, Pt

	doc = Document()
	section = doc.sections[0]
	section.page_width = Mm(210)
	section.page_height = Mm(297)
	section.top_margin = Mm(10)
	section.bottom_margin = Mm(12)
	section.left_margin = Mm(10)
	section.right_margin = Mm(10)
	styles = doc.styles
	styles["Normal"].font.name = "Arial"
	styles["Normal"].font.size = Pt(9)

	title = doc.add_paragraph()
	title.alignment = WD_ALIGN_PARAGRAPH.CENTER
	run = title.add_run(data["title"])
	run.bold = True
	run.font.size = Pt(16)
	copy = doc.add_paragraph(data["copy_label"])
	copy.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	copy.paragraph_format.space_after = Pt(3)

	header = doc.add_table(rows=2, cols=2)
	header.alignment = WD_TABLE_ALIGNMENT.CENTER
	header.style = "Table Grid"
	_set_table_widths(header, (95, 95))
	_add_party_cell(header.cell(0, 0), _("Supplier Details"), data["supplier"], data["invoice_type"])
	header_lines = [
		(_("Invoice No."), data["invoice_number"]),
		(_("Invoice Date"), data["invoice_date"]),
		(_("Buyer's Order No."), data["buyer_order_number"]),
		(_("Date"), data["buyer_order_date"]),
		(_("Supplier's Reference"), data["supplier_reference"]),
		(_("Despatch Document No."), data["dispatch_document_number"]),
		(_("Delivery Note Date"), data["delivery_note_date"]),
	]
	_add_lines(header.cell(0, 1), header_lines, include_empty=True)
	_add_party_cell(header.cell(1, 0), _("Consignee's Details"), data["consignee"], "GST")
	_add_party_cell(
		header.cell(1, 1),
		_("Buyer's Details (if other than Consignee)"),
		data["buyer"],
		"GST",
	)
	for row in header.rows:
		for cell in row.cells:
			cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

	doc.add_paragraph()
	table = doc.add_table(rows=1, cols=6)
	table.style = "Table Grid"
	table.alignment = WD_TABLE_ALIGNMENT.CENTER
	_set_table_widths(table, (11, 80, 23, 15, 27, 34))
	repeat_header = OxmlElement("w:tblHeader")
	table.rows[0]._tr.get_or_add_trPr().append(repeat_header)
	for cell, text in zip(
		table.rows[0].cells,
		[
			_("Sr. No."),
			_("Description"),
			_("HSN / SAC"),
			_("Qty."),
			_("Rate"),
			_("Amount (INR)"),
		],
		strict=True,
	):
		cell.text = str(text)
		for run in cell.paragraphs[0].runs:
			run.bold = True
	for item in data["items"]:
		cells = table.add_row().cells
		values = [
			item["number"],
			item["description"],
			item["hsn_sac"],
			_quantity_text(item["quantity"]),
			_money_text(item["rate"]),
			_money_text(item["amount"]),
		]
		for index, (cell, value) in enumerate(zip(cells, values, strict=True)):
			cell.text = str(value)
			if index >= 3:
				cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

	summary = [
		(_("Total"), data["items_total"]),
	]
	if data["invoice_type"] == "GST":
		summary.append((_("GST"), data["gst_amount"]))
	summary.extend(
		[
			(_("Transportation"), data["transportation_charges"]),
			(_("Others"), data["other_charges"]),
		]
	)
	for label, amount in summary:
		_add_summary_row(table, label, amount, bold=False)
	_add_summary_row(table, _("Grand Total"), data["grand_total"], bold=True)

	p = doc.add_paragraph()
	p.add_run(f"{_('Amount in words')}: ").bold = True
	p.add_run(data["amount_in_words"])
	if data["declaration"]:
		p = doc.add_paragraph()
		p.add_run(f"{data['declaration_title']}: ").bold = True
		p.add_run(data["declaration"])

	footer = doc.add_table(rows=1, cols=2)
	footer.style = "Table Grid"
	footer.alignment = WD_TABLE_ALIGNMENT.CENTER
	_set_table_widths(footer, (95, 95))
	bank_lines = [
		(_("Bank Name"), data["bank"]["bank_name"]),
		(_("Branch"), data["bank"]["branch"]),
		(_("Account Name"), data["bank"]["account_name"]),
		(_("Account No."), data["bank"]["account_number"]),
		(_("IFSC Code"), data["bank"]["ifsc"]),
		(_("Swift Code"), data["bank"]["swift"]),
	]
	footer.cell(0, 0).text = str(_("Remittance Details"))
	footer.cell(0, 0).paragraphs[0].runs[0].bold = True
	_add_lines(footer.cell(0, 0), bank_lines, include_empty=True)
	sig = footer.cell(0, 1)
	sig.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
	sig.paragraphs[0].add_run(data["signature_context"]).bold = True
	for _index in range(3):
		sig.add_paragraph()
	p = sig.add_paragraph(data["signatory_name"])
	p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	if data["signature_employee"]:
		p = sig.add_paragraph(data["signature_employee"])
		p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	p = sig.add_paragraph(data["signature_label"])
	p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	for current_table in (header, table, footer):
		for row in current_table.rows:
			no_split = OxmlElement("w:cantSplit")
			row._tr.get_or_add_trPr().append(no_split)

	buffer = BytesIO()
	doc.save(buffer)
	return buffer.getvalue()


def _set_table_widths(table, widths_mm):
	from docx.shared import Mm

	table.autofit = False
	for column, width in zip(table.columns, widths_mm, strict=True):
		column.width = Mm(width)
	for row in table.rows:
		for cell, width in zip(row.cells, widths_mm, strict=True):
			cell.width = Mm(width)


def _add_party_cell(cell, heading, party, invoice_type):
	cell.text = ""
	p = cell.paragraphs[0]
	p.add_run(str(heading)).bold = True
	p = cell.add_paragraph(party["name"])
	p.runs[0].bold = True
	for value in (party["address"], " ".join(filter(None, [party["state"], party["pin_code"]]))):
		if value:
			cell.add_paragraph(value)
	identity_label = _("GSTIN / UID No.") if invoice_type == "GST" else _("PAN No.")
	identity = party["gstin"] if invoice_type == "GST" else party["pan"]
	p = cell.add_paragraph()
	p.add_run(f"{identity_label}: ").bold = True
	p.add_run(identity)


def _add_lines(cell, lines, include_empty=False):
	for label, value in lines:
		if not value and not include_empty:
			continue
		p = cell.add_paragraph()
		p.add_run(f"{label}: ").bold = True
		p.add_run(str(value))


def _add_summary_row(table, label, amount, bold):
	cells = table.add_row().cells
	merged = cells[0].merge(cells[4])
	merged.text = str(label)
	merged.paragraphs[0].alignment = 2
	cells[5].text = _money_text(amount)
	cells[5].paragraphs[0].alignment = 2
	if bold:
		for cell in (merged, cells[5]):
			for run in cell.paragraphs[0].runs:
				run.bold = True
