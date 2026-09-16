# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

"""Employee-facing GST and non-GST invoice document generator.

This module deliberately does not create an ERP accounting document. It returns
an in-memory PDF and DOCX so the employee can obtain the supplier's verification
and signature before attaching the signed invoice to an Expense Claim.
"""

from __future__ import annotations

import base64
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from io import BytesIO

import frappe
from frappe import _
from frappe.contacts.doctype.address.address import get_default_address
from frappe.utils import formatdate, getdate, money_in_words, nowdate
from markupsafe import escape

from volunteering.volunteering.authority import get_employee_for_user

MAX_ITEMS = 20
MONEY_PLACES = Decimal("0.01")
MAX_MONEY = Decimal("999999999999.99")
MAX_QUANTITY = Decimal("999999999")
ALLOWED_TYPES = {"GST", "NON_GST"}
ALLOWED_TAX_MODES = {"CGST_SGST", "IGST"}
GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_PATTERN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


@frappe.whitelist(methods=["POST"])
def get_invoice_generator_defaults():
	employee = _require_employee()
	company = frappe.db.get_value("Employee", employee, "company")
	company_doc = frappe.get_cached_doc("Company", company)
	address = _company_address(company)
	return {
		"employee": employee,
		"company": company,
		"invoice_date": nowdate(),
		"consignee": {
			"name": company_doc.company_name or company,
			"address": address.get("address", ""),
			"state": address.get("state", ""),
			"pin_code": address.get("pincode", ""),
			"gstin": (company_doc.get("tax_id") or "").strip().upper(),
		},
	}


@frappe.whitelist(methods=["POST"])
def generate_invoice_documents(payload):
	"""Validate invoice data and return private, in-memory PDF and DOCX downloads."""
	_require_employee()
	data = _normalise_payload(payload)
	pdf_bytes = _build_pdf(data)
	docx_bytes = _build_docx(data)
	stem = _safe_filename(data["invoice_number"])
	return {
		"pdf": _download(f"{stem}.pdf", "application/pdf", pdf_bytes),
		"docx": _download(
			f"{stem}.docx",
			"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
			docx_bytes,
		),
		"grand_total": float(data["grand_total"]),
		"amount_in_words": data["amount_in_words"],
		"notice": _(
			"The supplier must verify and sign the generated invoice before it is attached to an Expense Claim."
		),
	}


def _require_employee():
	user = frappe.session.user
	if not user or user == "Guest":
		frappe.throw(_("Log in as an employee to prepare an invoice."), frappe.PermissionError)
	employee = get_employee_for_user(user)
	if not employee:
		frappe.throw(_("Your user must be linked to an active Employee record."), frappe.PermissionError)
	return employee


def _company_address(company):
	address_name = get_default_address("Company", company)
	if not address_name:
		return {}
	address = frappe.get_cached_doc("Address", address_name)
	lines = [
		address.get("address_line1"),
		address.get("address_line2"),
		address.get("city"),
		address.get("county"),
	]
	return {
		"address": ", ".join(str(value).strip() for value in lines if value),
		"state": address.get("state") or "",
		"pincode": address.get("pincode") or "",
	}


def _normalise_payload(payload):
	raw = frappe.parse_json(payload) if isinstance(payload, str) else payload
	if not isinstance(raw, dict):
		frappe.throw(_("Invoice details must be a valid object."))

	invoice_type = _required_choice(raw, "invoice_type", ALLOWED_TYPES, _("Invoice type"))
	data = {
		"invoice_type": invoice_type,
		"title": "TAX INVOICE" if invoice_type == "GST" else "INVOICE",
		"invoice_number": _required_text(raw, "invoice_number", _("Invoice number"), 80),
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
		"bank": _bank(raw.get("bank")),
		"authorised_signatory": _text(raw.get("authorised_signatory"), 120),
	}
	data["buyer"] = (
		data["consignee"]
		if data["buyer_same_as_consignee"]
		else _party(raw.get("buyer"), _("Buyer"))
	)

	if invoice_type == "GST":
		_validate_gstin(data["supplier"].get("gstin"), _("Supplier GSTIN"), required=True)
		_validate_gstin(data["consignee"].get("gstin"), _("Consignee GSTIN"), required=False)
		if len(data["invoice_number"]) > 16:
			frappe.throw(_("A GST invoice number cannot exceed 16 characters."))
		data["tax_mode"] = _required_choice(raw, "tax_mode", ALLOWED_TAX_MODES, _("GST type"))
		data["gst_rate"] = _rate(raw.get("gst_rate"))
		data["place_of_supply"] = _text(raw.get("place_of_supply"), 100) or data["consignee"]["state"]
		data["reverse_charge"] = bool(raw.get("reverse_charge"))
	else:
		_validate_pan(data["supplier"].get("pan"))
		data["tax_mode"] = ""
		data["gst_rate"] = Decimal("0")
		data["place_of_supply"] = ""
		data["reverse_charge"] = False

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
				"description": _required_text(raw_item, "description", _("Description in row {0}").format(index), 300),
				"hsn_sac": _required_text(raw_item, "hsn_sac", _("HSN/SAC in row {0}").format(index), 30),
				"unit": _required_text(raw_item, "unit", _("Unit in row {0}").format(index), 20),
				"quantity": quantity,
				"rate": rate,
				"amount": _quantise(line_amount),
			}
		)

	if not raw.get("supplier_confirmation_required"):
		frappe.throw(_("Confirm that the supplier will verify and sign the invoice."))

	data["items_total"] = _quantise(sum((item["amount"] for item in data["items"]), Decimal("0")))
	taxable_total = data["items_total"] + data["transportation_charges"] + data["other_charges"]
	if taxable_total > MAX_MONEY:
		frappe.throw(_("Invoice total is too large."))
	data["taxable_total"] = _quantise(taxable_total)
	data["gst_amount"] = _quantise(data["taxable_total"] * data["gst_rate"] / Decimal("100"))
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
	data["non_gst_declaration"] = _(
		"I, {0}, proprietor/authorised person of {1}, declare that this business is not registered "
		"under the Goods and Services Tax (GST) Act and therefore does not have a GSTIN."
	).format(data["authorised_signatory"] or _("the undersigned"), data["supplier"]["name"])
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
	except (InvalidOperation, ValueError):
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
	if not value or not PAN_PATTERN.fullmatch(value):
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
		f"<td>{h(item['hsn_sac'])}</td><td>{h(item['unit'])}</td><td class='num'>{_quantity_text(item['quantity'])}</td>"
		f"<td class='num'>{_money_text(item['rate'])}</td><td class='num'>{_money_text(item['amount'])}</td></tr>"
		for item in data["items"]
	)
	summary = [
		(_("Items subtotal"), data["items_total"]),
		(_("Transportation"), data["transportation_charges"]),
		(_("Other charges"), data["other_charges"]),
	]
	if data["tax_mode"] == "CGST_SGST":
		half_rate = data["gst_rate"] / Decimal("2")
		summary.extend(
			[
				(_("CGST @ {0}%").format(half_rate), data["cgst_amount"]),
				(_("SGST @ {0}%").format(half_rate), data["sgst_amount"]),
			]
		)
	elif data["tax_mode"] == "IGST":
		summary.append((_("IGST @ {0}%").format(data["gst_rate"]), data["igst_amount"]))
	summary_rows = "".join(
		f"<tr><td colspan='6' class='summary-label'>{h(label)}</td><td class='num'>{_money_text(value)}</td></tr>"
		for label, value in summary
		if value or label == _("Items subtotal")
	)
	bank = data["bank"]
	bank_lines = [
		(_("Bank"), bank["bank_name"]),
		(_("Branch"), bank["branch"]),
		(_("Account name"), bank["account_name"]),
		(_("Account number"), bank["account_number"]),
		(_("IFSC"), bank["ifsc"]),
		(_("SWIFT"), bank["swift"]),
	]
	bank_html = "<br>".join(f"<b>{h(label)}:</b> {h(value)}" for label, value in bank_lines if value)
	declaration = (
		f"<div class='declaration'><b>{h(_('Non-GST declaration'))}:</b> {h(data['non_gst_declaration'])}</div>"
		if data["invoice_type"] == "NON_GST"
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
.party {{ width: 50%; }}
.label {{ color: #555; font-size: 8pt; text-transform: uppercase; }}
.value {{ font-weight: 600; margin-top: 1px; }}
.num {{ text-align: right; white-space: nowrap; }}
.summary-label {{ text-align: right; font-weight: 600; }}
.grand td {{ font-size: 11pt; font-weight: 700; background: #f2f2f2; }}
.section {{ margin-top: 3mm; }}
.declaration {{ border: 1px solid #555; padding: 5px; margin-top: 3mm; }}
.signature {{ height: 22mm; text-align: right; }}
.notice {{ margin-top: 3mm; padding-top: 2mm; border-top: 1px solid #777; font-size: 8pt; color: #444; }}
</style></head><body>
<h1>{h(data['title'])}</h1><div class="copy">{h(_('Original for recipient'))}</div>
<table><tr><td class="party"><div class="label">{h(_('Supplier'))}</div><div class="value">{h(data['supplier']['name'])}</div>{h(data['supplier']['address'])}<br>{h(data['supplier']['state'])} {h(data['supplier']['pin_code'])}<br>{h(_('GSTIN')) if data['invoice_type'] == 'GST' else h(_('PAN'))}: {h(data['supplier']['gstin'] if data['invoice_type'] == 'GST' else data['supplier']['pan'])}</td>
<td><b>{h(_('Invoice number'))}:</b> {h(data['invoice_number'])}<br><b>{h(_('Invoice date'))}:</b> {h(data['invoice_date'])}<br><b>{h(_('Buyer order'))}:</b> {h(data['buyer_order_number'])} {h(data['buyer_order_date'])}<br><b>{h(_('Supplier reference'))}:</b> {h(data['supplier_reference'])}<br><b>{h(_('Dispatch document'))}:</b> {h(data['dispatch_document_number'])}<br><b>{h(_('Delivery note date'))}:</b> {h(data['delivery_note_date'])}{f'<br><b>{h(_("Place of supply"))}:</b> {h(data["place_of_supply"])}<br><b>{h(_("Reverse charge"))}:</b> {h(_("Yes") if data["reverse_charge"] else _("No"))}' if data['invoice_type'] == 'GST' else ''}</td></tr>
<tr><td><div class="label">{h(_('Consignee'))}</div><div class="value">{h(data['consignee']['name'])}</div>{h(data['consignee']['address'])}<br>{h(data['consignee']['state'])} {h(data['consignee']['pin_code'])}<br>{h(_('GSTIN'))}: {h(data['consignee']['gstin'])}</td>
<td><div class="label">{h(_('Buyer'))}</div><div class="value">{h(buyer['name'])}</div>{h(buyer['address'])}<br>{h(buyer['state'])} {h(buyer['pin_code'])}<br>{h(_('GSTIN'))}: {h(buyer['gstin'])}</td></tr></table>
<table class="section"><thead><tr><th>{h(_('Sr.'))}</th><th>{h(_('Description'))}</th><th>{h(_('HSN/SAC'))}</th><th>{h(_('Unit'))}</th><th>{h(_('Qty'))}</th><th>{h(_('Rate (INR)'))}</th><th>{h(_('Amount (INR)'))}</th></tr></thead><tbody>{items}{summary_rows}<tr class="grand"><td colspan="6" class="summary-label">{h(_('Grand total'))}</td><td class="num">{_money_text(data['grand_total'])}</td></tr></tbody></table>
<div class="declaration"><b>{h(_('Amount in words'))}:</b> {h(data['amount_in_words'])}</div>{declaration}
<table class="section"><tr><td class="party"><b>{h(_('Remittance details'))}</b><br>{bank_html or h(_('Not provided'))}</td><td class="signature"><b>{h(_('For'))} {h(data['supplier']['name'])}</b><br><br><br>{h(data['authorised_signatory'])}<br>{h(_('Authorised signatory and supplier signature'))}</td></tr></table>
<div class="notice">{h(_('Prepared using Sevamrita invoice assistance. Valid for reimbursement only after the supplier verifies the details and signs the document.'))}</div>
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
			frappe.throw(
				_("PDF generation is unavailable because no supported PDF renderer is installed.")
			)
		return HTML(string=html).write_pdf()


def _build_docx(data):
	from docx import Document
	from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
	from docx.enum.text import WD_ALIGN_PARAGRAPH
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
	copy = doc.add_paragraph(_("Original for recipient"))
	copy.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	copy.paragraph_format.space_after = Pt(3)

	header = doc.add_table(rows=2, cols=2)
	header.alignment = WD_TABLE_ALIGNMENT.CENTER
	header.style = "Table Grid"
	_add_party_cell(header.cell(0, 0), _("Supplier"), data["supplier"], data["invoice_type"])
	header_lines = [
			(_("Invoice number"), data["invoice_number"]),
			(_("Invoice date"), data["invoice_date"]),
			(_("Buyer order"), " ".join(filter(None, [data["buyer_order_number"], data["buyer_order_date"]]))),
			(_("Supplier reference"), data["supplier_reference"]),
			(_("Dispatch document"), data["dispatch_document_number"]),
			(_("Delivery note date"), data["delivery_note_date"]),
	]
	if data["invoice_type"] == "GST":
		header_lines.extend(
			[
				(_("Place of supply"), data["place_of_supply"]),
				(_("Reverse charge"), _("Yes") if data["reverse_charge"] else _("No")),
			]
		)
	_add_lines(header.cell(0, 1), header_lines)
	_add_party_cell(header.cell(1, 0), _("Consignee"), data["consignee"], "GST")
	_add_party_cell(header.cell(1, 1), _("Buyer"), data["buyer"], "GST")
	for row in header.rows:
		for cell in row.cells:
			cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.TOP

	doc.add_paragraph()
	table = doc.add_table(rows=1, cols=7)
	table.style = "Table Grid"
	table.alignment = WD_TABLE_ALIGNMENT.CENTER
	for cell, text in zip(
		table.rows[0].cells,
		[
			_("Sr."),
			_("Description"),
			_("HSN/SAC"),
			_("Unit"),
			_("Qty"),
			_("Rate (INR)"),
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
			item["unit"],
			_quantity_text(item["quantity"]),
			_money_text(item["rate"]),
			_money_text(item["amount"]),
		]
		for index, (cell, value) in enumerate(zip(cells, values, strict=True)):
			cell.text = str(value)
			if index >= 4:
				cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

	summary = [
		(_("Items subtotal"), data["items_total"]),
		(_("Transportation"), data["transportation_charges"]),
		(_("Other charges"), data["other_charges"]),
	]
	if data["tax_mode"] == "CGST_SGST":
		half_rate = data["gst_rate"] / Decimal("2")
		summary.extend(
			[
				(_("CGST @ {0}%").format(half_rate), data["cgst_amount"]),
				(_("SGST @ {0}%").format(half_rate), data["sgst_amount"]),
			]
		)
	elif data["tax_mode"] == "IGST":
		summary.append((_("IGST @ {0}%").format(data["gst_rate"]), data["igst_amount"]))
	for label, amount in summary:
		if not amount and label != _("Items subtotal"):
			continue
		_add_summary_row(table, label, amount, bold=False)
	_add_summary_row(table, _("Grand total"), data["grand_total"], bold=True)

	p = doc.add_paragraph()
	p.add_run(f"{_('Amount in words')}: ").bold = True
	p.add_run(data["amount_in_words"])
	if data["invoice_type"] == "NON_GST":
		p = doc.add_paragraph()
		p.add_run(f"{_('Non-GST declaration')}: ").bold = True
		p.add_run(data["non_gst_declaration"])

	footer = doc.add_table(rows=1, cols=2)
	footer.style = "Table Grid"
	bank_lines = [
		(_("Bank"), data["bank"]["bank_name"]),
		(_("Branch"), data["bank"]["branch"]),
		(_("Account name"), data["bank"]["account_name"]),
		(_("Account number"), data["bank"]["account_number"]),
		(_("IFSC"), data["bank"]["ifsc"]),
		(_("SWIFT"), data["bank"]["swift"]),
	]
	footer.cell(0, 0).text = str(_("Remittance details"))
	footer.cell(0, 0).paragraphs[0].runs[0].bold = True
	_add_lines(footer.cell(0, 0), bank_lines)
	sig = footer.cell(0, 1)
	sig.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
	sig.paragraphs[0].add_run(f"{_('For')} {data['supplier']['name']}").bold = True
	for _index in range(3):
		sig.add_paragraph()
	p = sig.add_paragraph(data["authorised_signatory"])
	p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
	p = sig.add_paragraph(_("Authorised signatory and supplier signature"))
	p.alignment = WD_ALIGN_PARAGRAPH.RIGHT

	notice = doc.add_paragraph(
		_(
			"Prepared using Sevamrita invoice assistance. Valid for reimbursement only after the supplier verifies the details and signs the document."
		)
	)
	notice.paragraph_format.space_before = Pt(5)
	for run in notice.runs:
		run.italic = True
		run.font.size = Pt(8)

	buffer = BytesIO()
	doc.save(buffer)
	return buffer.getvalue()


def _add_party_cell(cell, heading, party, invoice_type):
	cell.text = ""
	p = cell.paragraphs[0]
	p.add_run(str(heading)).bold = True
	p = cell.add_paragraph(party["name"])
	p.runs[0].bold = True
	for value in (party["address"], " ".join(filter(None, [party["state"], party["pin_code"]]))):
		if value:
			cell.add_paragraph(value)
	identity_label = _("GSTIN") if invoice_type == "GST" else _("PAN")
	identity = party["gstin"] if invoice_type == "GST" else party["pan"]
	if identity:
		p = cell.add_paragraph()
		p.add_run(f"{identity_label}: ").bold = True
		p.add_run(identity)


def _add_lines(cell, lines):
	for label, value in lines:
		if not value:
			continue
		p = cell.add_paragraph()
		p.add_run(f"{label}: ").bold = True
		p.add_run(str(value))


def _add_summary_row(table, label, amount, bold):
	cells = table.add_row().cells
	merged = cells[0].merge(cells[5])
	merged.text = str(label)
	merged.paragraphs[0].alignment = 2
	cells[6].text = _money_text(amount)
	cells[6].paragraphs[0].alignment = 2
	if bold:
		for cell in (merged, cells[6]):
			for run in cell.paragraphs[0].runs:
				run.bold = True
