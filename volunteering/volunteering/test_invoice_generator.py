# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from decimal import Decimal
from io import BytesIO

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.invoice_generator import (
	_build_docx,
	_normalise_payload,
	_render_pdf_html,
	_safe_filename,
)


def _payload(invoice_type="GST"):
	return {
		"invoice_type": invoice_type,
		"invoice_number": "INV/2026/001",
		"invoice_date": "2026-09-16",
		"supplier": {
			"name": "Example Kitchen Supplies",
			"address": "12 Market Road, Mumbai",
			"state": "Maharashtra",
			"pin_code": "400001",
			"gstin": "27ABCDE1234F1Z5",
			"pan": "ABCDE1234F",
		},
		"consignee": {
			"name": "Sevamrita Foundation",
			"address": "1 Service Road, Mumbai",
			"state": "Maharashtra",
			"pin_code": "400002",
			"gstin": "27AAECS1234F1Z5",
		},
		"buyer_same_as_consignee": True,
		"items": [
			{
				"description": "Steel utensils",
				"hsn_sac": "7323",
				"unit": "Nos",
				"quantity": 2,
				"rate": 100,
			},
		],
		"transportation_charges": 10,
		"other_charges": 0,
		"tax_mode": "CGST_SGST",
		"gst_rate": 18,
		"place_of_supply": "Maharashtra",
		"reverse_charge": False,
		"authorised_signatory": "Asha Vendor",
		"supplier_confirmation_required": True,
	}


class UnitTestInvoiceGenerator(UnitTestCase):
	def test_gst_totals_are_recalculated_on_server(self):
		data = _normalise_payload(_payload())
		self.assertEqual(data["items_total"], Decimal("200.00"))
		self.assertEqual(data["taxable_total"], Decimal("210.00"))
		self.assertEqual(data["gst_amount"], Decimal("37.80"))
		self.assertEqual(data["cgst_amount"], Decimal("18.90"))
		self.assertEqual(data["sgst_amount"], Decimal("18.90"))
		self.assertEqual(data["grand_total"], Decimal("247.80"))

	def test_non_gst_requires_pan_and_adds_declaration(self):
		payload = _payload("NON_GST")
		data = _normalise_payload(payload)
		self.assertEqual(data["gst_amount"], Decimal("0.00"))
		self.assertIn("not registered", data["non_gst_declaration"])
		self.assertIn("Example Kitchen Supplies", data["non_gst_declaration"])

	def test_supplier_confirmation_is_mandatory(self):
		payload = _payload()
		payload["supplier_confirmation_required"] = False
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)

	def test_gst_invoice_number_is_limited_to_sixteen_characters(self):
		payload = _payload()
		payload["invoice_number"] = "GST-INVOICE-TOO-LONG"
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)

	def test_non_finite_amount_is_rejected(self):
		payload = _payload()
		payload["items"][0]["rate"] = "NaN"
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)

	def test_html_escapes_supplier_content(self):
		payload = _payload()
		payload["supplier"]["name"] = "Vendor <script>alert(1)</script>"
		html = _render_pdf_html(_normalise_payload(payload))
		self.assertNotIn("<script>", html)
		self.assertIn("&lt;script&gt;", html)

	def test_docx_contains_invoice_identity_and_total(self):
		from docx import Document

		content = _build_docx(_normalise_payload(_payload()))
		document = Document(BytesIO(content))
		text = "\n".join(
			[paragraph.text for paragraph in document.paragraphs]
			+ [cell.text for table in document.tables for row in table.rows for cell in row.cells]
		)
		self.assertIn("TAX INVOICE", text)
		self.assertIn("INV/2026/001", text)
		self.assertIn("247.80", text)
		self.assertIn("supplier verifies", text)

	def test_safe_filename_removes_path_characters(self):
		self.assertEqual(_safe_filename("../../INV 001"), "invoice-INV-001")
