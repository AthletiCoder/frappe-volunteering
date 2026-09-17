# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import base64
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering import invoice_generator as invoices
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
		"signer_type": "SUPPLIER",
	}


class UnitTestInvoiceGenerator(UnitTestCase):
	def test_generation_retries_transaction_conflict(self):
		result = {"invoice_number": "INV-2098-000001"}
		with (
			patch.object(
				invoices,
				"_generate_invoice_documents",
				side_effect=[frappe.QueryDeadlockError("conflict"), result],
			) as generate,
			patch.object(frappe.db, "rollback") as rollback,
		):
			self.assertEqual(invoices.generate_invoice_documents({}), result)
		self.assertEqual(generate.call_count, 2)
		rollback.assert_called_once_with()

	def test_generation_transaction_retries_are_bounded(self):
		with (
			patch.object(
				invoices, "_generate_invoice_documents", side_effect=frappe.QueryDeadlockError("conflict")
			) as generate,
			patch.object(frappe.db, "rollback") as rollback,
		):
			with self.assertRaisesRegex(frappe.ValidationError, "generation is busy"):
				invoices.generate_invoice_documents({})
		self.assertEqual(generate.call_count, 3)
		self.assertEqual(rollback.call_count, 3)

	def test_gst_totals_are_recalculated_on_server(self):
		data = _normalise_payload(_payload())
		self.assertEqual(data["items_total"], Decimal("200.00"))
		self.assertEqual(data["taxable_total"], Decimal("210.00"))
		self.assertEqual(data["gst_amount"], Decimal("37.80"))
		self.assertEqual(data["cgst_amount"], Decimal("18.90"))
		self.assertEqual(data["sgst_amount"], Decimal("18.90"))
		self.assertEqual(data["grand_total"], Decimal("247.80"))

	def test_supplier_non_gst_has_no_tax_and_has_registration_declaration(self):
		payload = _payload("NON_GST")
		data = _normalise_payload(payload)
		self.assertEqual(data["gst_amount"], Decimal("0.00"))
		self.assertIn("not registered", data["declaration"])
		self.assertIn("Example Kitchen Supplies", data["declaration"])
		self.assertEqual(data["declaration_title"], "Non-GST declaration")

	def test_non_gst_pan_is_optional_but_checked_when_supplied(self):
		payload = _payload("NON_GST")
		payload["supplier"].pop("pan")
		self.assertEqual(_normalise_payload(payload)["supplier"]["pan"], "")
		payload["supplier"]["pan"] = "INVALID"
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)

	def test_signer_acknowledgment_is_not_required_for_either_signer(self):
		for signer in ("SUPPLIER", "VOLUNTEER"):
			for confirmation in (None, False, "false"):
				with self.subTest(signer=signer, confirmation=confirmation):
					payload = _payload()
					payload["signer_type"] = signer
					if confirmation is not None:
						# Ignore old form acknowledgment values; they are no longer required.
						payload["signature_confirmation_required"] = confirmation
					data = _normalise_payload(
						payload, volunteer_override={"name": "Test Volunteer", "employee": "HR-EMP-TEST"}
					)
					self.assertEqual(data["signer_type"], signer)

	def test_legacy_client_without_signer_defaults_to_supplier(self):
		payload = _payload()
		payload.pop("signer_type")
		payload["supplier_confirmation_required"] = False
		self.assertEqual(_normalise_payload(payload)["signer_type"], "SUPPLIER")

	def test_hsn_sac_is_optional_for_both_invoice_types_and_signers(self):
		for invoice_type in ("NON_GST", "GST"):
			for signer in ("SUPPLIER", "VOLUNTEER"):
				for code in (None, "", "   ", "7323"):
					with self.subTest(invoice_type=invoice_type, signer=signer, code=code):
						payload = _payload(invoice_type)
						payload["signer_type"] = signer
						if code is None:
							payload["items"][0].pop("hsn_sac")
						else:
							payload["items"][0]["hsn_sac"] = code
						data = _normalise_payload(
							payload,
							volunteer_override={"name": "Test Volunteer", "employee": "HR-EMP-TEST"},
						)
						self.assertEqual(data["items"][0]["hsn_sac"], "7323" if code == "7323" else "")

	def test_invalid_signer_or_missing_volunteer_identity_is_rejected(self):
		payload = _payload()
		payload["signer_type"] = "ANYONE"
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)
		payload["signer_type"] = "VOLUNTEER"
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)

	def test_volunteer_signing_never_makes_supplier_declarations_in_either_document(self):
		from docx import Document

		for invoice_type in ("NON_GST", "GST"):
			with self.subTest(invoice_type=invoice_type):
				payload = _payload(invoice_type)
				payload["signer_type"] = "VOLUNTEER"
				payload["volunteer"] = {"name": "Forged Volunteer", "employee": "Forged Employee"}
				data = _normalise_payload(
					payload, volunteer_override={"name": "Test Volunteer", "employee": "HR-EMP-TEST"}
				)
				self.assertEqual(data["authorised_signatory"], "")
				self.assertIn("EXPENSE STATEMENT", data["title"])
				document = Document(BytesIO(_build_docx(data)))
				word_text = "\n".join(
					[p.text for p in document.paragraphs]
					+ [cell.text for table in document.tables for row in table.rows for cell in row.cells]
				)
				for text in (_render_pdf_html(data), word_text):
					self.assertIn("Volunteer declaration", text)
					self.assertIn("Volunteer signature", text)
					self.assertIn("Test Volunteer", text)
					self.assertIn("HR-EMP-TEST", text)
					self.assertNotIn("Forged", text)
					self.assertNotIn("Asha Vendor", text)
					self.assertNotIn("not registered", text)
					self.assertNotIn("Non-GST declaration", text)
					self.assertNotIn("Authorised signatory and supplier signature", text)
					self.assertNotIn("TAX INVOICE", text)
					if invoice_type == "GST":
						self.assertIn("does not replace a supplier-issued GST tax invoice", text)

	def test_supplier_non_gst_declaration_is_conditional_in_both_documents(self):
		from docx import Document

		for invoice_type in ("NON_GST", "GST"):
			for signatory in ("Asha Vendor", ""):
				with self.subTest(invoice_type=invoice_type, signatory=signatory):
					payload = _payload(invoice_type)
					payload["authorised_signatory"] = signatory
					data = _normalise_payload(payload)
					doc = Document(BytesIO(_build_docx(data)))
					word_text = "\n".join(
						[p.text for p in doc.paragraphs]
						+ [cell.text for table in doc.tables for row in table.rows for cell in row.cells]
					)
					for text in (_render_pdf_html(data), word_text):
						if invoice_type == "NON_GST":
							self.assertIn("Non-GST declaration", text)
							self.assertIn("not registered", text)
							self.assertIn("does not have a GSTIN", text)
							self.assertIn(signatory or "the undersigned", text)
						else:
							self.assertNotIn("Non-GST declaration", text)
							self.assertNotIn("not registered", text)
						self.assertIn("Authorised signatory and supplier signature", text)
						self.assertNotIn("Volunteer declaration", text)

	def test_gst_invoice_number_is_limited_to_sixteen_characters(self):
		payload = _payload()
		payload["invoice_number"] = "GST-INVOICE-TOO-LONG"
		with self.assertRaises(frappe.ValidationError):
			_normalise_payload(payload)

	def test_generated_number_override_does_not_require_browser_number(self):
		payload = _payload()
		payload.pop("invoice_number")
		data = _normalise_payload(payload, invoice_number_override="INV-2098-000001")
		self.assertEqual(data["invoice_number"], "INV-2098-000001")

	def test_generated_number_override_ignores_browser_number(self):
		payload = _payload()
		payload["invoice_number"] = "FORGED-NUMBER-THAT-IS-TOO-LONG-FOR-GST"
		data = _normalise_payload(payload, invoice_number_override="INV-2098-000001")
		self.assertEqual(data["invoice_number"], "INV-2098-000001")

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
		self.assertIn("Ask the supplier to verify", text)

	def test_safe_filename_removes_path_characters(self):
		self.assertEqual(_safe_filename("../../INV 001"), "invoice-INV-001")


class IntegrationTestGeneratedInvoiceNumbers(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.db.savepoint("generated_invoice_test")
		# Use future years under a rollback-only test transaction; existing counters
		# (if any) are restored, and the live generation year's counter is untouched.
		for year in (2098, 2099):
			frappe.db.sql(
				"UPDATE `tabSeries` SET `current`=0 WHERE `name`=%s",
				(f"SEVAMRITA-FORM-INVOICE-{year}-",),
			)

	def tearDown(self):
		frappe.db.rollback(save_point="generated_invoice_test")
		super().tearDown()

	def generation_context(self, pdf=None):
		from contextlib import ExitStack

		stack = ExitStack()
		stack.enter_context(patch.object(invoices, "nowdate", return_value="2098-12-31"))
		stack.enter_context(patch.object(invoices, "_require_employee", return_value="Test Employee"))
		stack.enter_context(
			patch.object(
				invoices,
				"_employee_signer",
				side_effect=lambda employee: {"employee": employee, "name": "Test Volunteer"},
			)
		)
		stack.enter_context(
			patch(
				"volunteering.volunteering.employee_bank_accounts.get_approved_bank_details",
				return_value={
					"bank_name": "Test Bank",
					"account_number": "1234567890",
					"ifsc": "TEST0123456",
				},
			)
		)
		stack.enter_context(
			patch.object(
				invoices,
				"_build_pdf",
				side_effect=pdf or (lambda data: invoices._render_pdf_html(data).encode()),
			)
		)
		return stack

	def test_sequence_is_shared_by_employee_and_invoice_type_and_generation_year(self):
		with self.generation_context():
			first = invoices.generate_invoice_documents(_payload("NON_GST"))
			with patch.object(invoices, "_require_employee", return_value="Another Employee"):
				second = invoices.generate_invoice_documents(_payload("GST"))
		self.assertEqual(first["invoice_number"], "INV-2098-000001")
		self.assertEqual(second["invoice_number"], "INV-2098-000002")

	def test_new_calendar_generation_year_starts_new_sequence(self):
		with patch.object(invoices, "nowdate", return_value="2098-12-31"):
			self.assertEqual(invoices._next_invoice_number(), "INV-2098-000001")
		with patch.object(invoices, "nowdate", return_value="2099-01-01"):
			self.assertEqual(invoices._next_invoice_number(), "INV-2099-000001")
		with patch.object(invoices, "nowdate", return_value="2098-12-31"):
			self.assertEqual(invoices._next_invoice_number(), "INV-2098-000002")

	def test_pdf_only_does_not_generate_word_and_word_reuses_number(self):
		payload = _payload("NON_GST")
		payload["supplier"].pop("pan")
		with self.generation_context(), patch.object(invoices, "_build_docx") as word:
			pdf = invoices.generate_invoice_documents(payload, output_format="pdf")
			word.assert_not_called()
			self.assertIn("pdf", pdf)
			self.assertNotIn("docx", pdf)
		with self.generation_context(), patch.object(invoices, "_build_pdf") as build_pdf:
			word = invoices.generate_invoice_documents(
				payload, output_format="docx", generation_reference=pdf["generation_reference"]
			)
			build_pdf.assert_not_called()
		self.assertIn("docx", word)
		self.assertNotIn("pdf", word)
		self.assertEqual(pdf["invoice_number"], word["invoice_number"])
		with self.generation_context():
			self.assertEqual(invoices._next_invoice_number(), "INV-2098-000002")

	def test_word_can_be_generated_first_without_pdf(self):
		with self.generation_context(), patch.object(invoices, "_build_pdf") as pdf:
			word = invoices.generate_invoice_documents(_payload(), output_format="docx")
			pdf.assert_not_called()
		self.assertIn("docx", word)
		self.assertNotIn("pdf", word)

	def test_volunteer_identity_is_server_assigned_and_signer_change_gets_new_number(self):
		payload = _payload("NON_GST")
		with self.generation_context():
			supplier = invoices.generate_invoice_documents(payload, output_format="pdf")
			payload["signer_type"] = "VOLUNTEER"
			payload["volunteer"] = {"name": "Forged Volunteer", "employee": "Forged Employee"}
			volunteer = invoices.generate_invoice_documents(
				payload, output_format="pdf", generation_reference=supplier["generation_reference"]
			)
			word = invoices.generate_invoice_documents(
				payload, output_format="docx", generation_reference=volunteer["generation_reference"]
			)
		self.assertEqual(supplier["invoice_number"], "INV-2098-000001")
		self.assertEqual(volunteer["invoice_number"], "INV-2098-000002")
		self.assertEqual(word["invoice_number"], volunteer["invoice_number"])
		html = base64.b64decode(volunteer["pdf"]["content_base64"]).decode()
		self.assertIn("Test Volunteer", html)
		self.assertIn("Test Employee", html)
		self.assertNotIn("Forged", html)
		self.assertNotIn("not registered", html)
		self.assertEqual(volunteer["signer_type"], "VOLUNTEER")
		self.assertIn("volunteer expense confirmation", volunteer["notice"])

	def test_changed_content_gets_new_number_not_reference_number(self):
		payload = _payload()
		with self.generation_context():
			first = invoices.generate_invoice_documents(payload, output_format="pdf")
			payload["items"][0]["rate"] = 200
			second = invoices.generate_invoice_documents(
				payload, output_format="docx", generation_reference=first["generation_reference"]
			)
		self.assertEqual(second["invoice_number"], "INV-2098-000002")

	def test_reference_cannot_be_forged_or_used_by_another_employee(self):
		with self.generation_context():
			first = invoices.generate_invoice_documents(_payload(), output_format="pdf")
			with self.assertRaises(frappe.ValidationError):
				invoices.generate_invoice_documents(
					_payload(), output_format="docx", generation_reference="FORGED"
				)
			with patch.object(invoices, "_require_employee", return_value="Another Employee"):
				with self.assertRaises(frappe.PermissionError):
					invoices.generate_invoice_documents(
						_payload(), output_format="docx", generation_reference=first["generation_reference"]
					)

	def test_invalid_format_does_not_consume_number(self):
		with self.generation_context():
			with self.assertRaises(frappe.ValidationError):
				invoices.generate_invoice_documents(_payload(), output_format="invalid")
			self.assertEqual(invoices._next_invoice_number(), "INV-2098-000001")

	def test_number_is_server_assigned_and_identical_in_both_documents_and_filenames(self):
		from docx import Document

		payload = _payload()
		payload["invoice_number"] = "FORGED-NUMBER-THAT-IS-TOO-LONG-FOR-GST"
		with self.generation_context():
			result = invoices.generate_invoice_documents(payload)
		self.assertEqual(result["invoice_number"], "INV-2098-000001")
		html = base64.b64decode(result["pdf"]["content_base64"]).decode()
		word = Document(BytesIO(base64.b64decode(result["docx"]["content_base64"])))
		text = "\n".join(cell.text for table in word.tables for row in table.rows for cell in row.cells)
		for content in (html, text):
			self.assertIn(result["invoice_number"], content)
			self.assertNotIn("FORGED-NUMBER", content)
		self.assertEqual(result["pdf"]["filename"], "invoice-INV-2098-000001.pdf")
		self.assertEqual(result["docx"]["filename"], "invoice-INV-2098-000001.docx")

	def test_invalid_payload_does_not_allocate_a_number(self):
		payload = _payload()
		payload.pop("invoice_number")
		payload["items"] = []
		with self.generation_context():
			with self.assertRaises(frappe.ValidationError):
				invoices.generate_invoice_documents(payload)
			self.assertEqual(
				invoices.generate_invoice_documents(_payload())["invoice_number"], "INV-2098-000001"
			)

	def test_failed_document_generation_rolls_back_number_with_request_transaction(self):
		frappe.db.savepoint("failed_generation_request")
		with (
			self.generation_context(),
			patch.object(invoices, "_build_docx", side_effect=RuntimeError("Render failed")),
		):
			with self.assertRaisesRegex(RuntimeError, "Render failed"):
				invoices.generate_invoice_documents(_payload())
		# Frappe rolls back unsuccessful POST requests, including the Series write.
		frappe.db.rollback(save_point="failed_generation_request")
		with self.generation_context():
			self.assertEqual(
				invoices.generate_invoice_documents(_payload())["invoice_number"], "INV-2098-000001"
			)
