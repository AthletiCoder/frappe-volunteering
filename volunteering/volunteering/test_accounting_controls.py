# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.accounting_controls import validate_payment_entry


class TestPaymentEntryControls(UnitTestCase):
	def _pe(self, party_type, refs):
		return frappe._dict(
			party_type=party_type,
			references=[frappe._dict(r) for r in refs],
		)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_supplier_pe_against_approved_po_allowed(self, mock_get_doc):
		po = frappe._dict(name="PO-1", workflow_state="Approved", docstatus=1)
		mock_get_doc.return_value = po
		doc = self._pe("Supplier", [{"reference_doctype": "Purchase Order", "reference_name": "PO-1"}])
		validate_payment_entry(doc)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_supplier_pe_against_unapproved_po_blocked(self, mock_get_doc):
		po = frappe._dict(name="PO-1", workflow_state="Pending Approval", docstatus=1)
		mock_get_doc.return_value = po
		doc = self._pe("Supplier", [{"reference_doctype": "Purchase Order", "reference_name": "PO-1"}])
		with self.assertRaises(frappe.ValidationError):
			validate_payment_entry(doc)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_supplier_pe_against_draft_po_blocked(self, mock_get_doc):
		po = frappe._dict(name="PO-1", workflow_state="Approved", docstatus=0)
		mock_get_doc.return_value = po
		doc = self._pe("Supplier", [{"reference_doctype": "Purchase Order", "reference_name": "PO-1"}])
		with self.assertRaises(frappe.ValidationError):
			validate_payment_entry(doc)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_supplier_pe_against_approved_pi_allowed(self, mock_get_doc):
		pi = frappe._dict(name="PINV-1", workflow_state="Approved", docstatus=1)
		mock_get_doc.return_value = pi
		doc = self._pe(
			"Supplier", [{"reference_doctype": "Purchase Invoice", "reference_name": "PINV-1"}]
		)
		validate_payment_entry(doc)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_supplier_pe_against_unapproved_pi_blocked(self, mock_get_doc):
		pi = frappe._dict(name="PINV-1", workflow_state="Draft", docstatus=0)
		mock_get_doc.return_value = pi
		doc = self._pe(
			"Supplier", [{"reference_doctype": "Purchase Invoice", "reference_name": "PINV-1"}]
		)
		with self.assertRaises(frappe.ValidationError):
			validate_payment_entry(doc)

	def test_supplier_pe_without_refs_blocked(self):
		doc = self._pe("Supplier", [])
		with self.assertRaises(frappe.ValidationError):
			validate_payment_entry(doc)

	def test_supplier_pe_wrong_ref_type_blocked(self):
		doc = self._pe("Supplier", [{"reference_doctype": "Sales Invoice", "reference_name": "SINV-1"}])
		with self.assertRaises(frappe.ValidationError):
			validate_payment_entry(doc)
