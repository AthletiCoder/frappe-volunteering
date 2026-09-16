# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.accounting_controls import (
	ensure_expense_claim_accounts,
	validate_payment_entry,
)


class TestExpenseClaimAccountControls(UnitTestCase):
	@patch("volunteering.volunteering.accounting_controls._company_payable_account")
	def test_hidden_payable_account_is_replaced_from_trusted_configuration(self, mock_payable_account):
		mock_payable_account.return_value = "Configured Payable - SF"
		doc = frappe._dict(
			doctype="Expense Claim",
			company="Sevamrita Foundation",
			payable_account="Client Supplied Payable - SF",
			expenses=[
				frappe._dict(
					expense_type="Travel",
					default_account="Client Supplied Expense - SF",
				)
			],
		)

		ensure_expense_claim_accounts(doc)

		self.assertEqual(doc.payable_account, "Configured Payable - SF")
		# Line accounts are owned by the Project-scoped selector, not this hook.
		self.assertEqual(doc.expenses[0].default_account, "Client Supplied Expense - SF")

	@patch("volunteering.volunteering.accounting_controls._company_payable_account")
	def test_missing_company_payable_account_is_rejected(self, mock_payable_account):
		mock_payable_account.return_value = None
		doc = frappe._dict(
			doctype="Expense Claim",
			company="Sevamrita Foundation",
			expenses=[],
		)

		with self.assertRaisesRegex(frappe.ValidationError, "No payable account is configured"):
			ensure_expense_claim_accounts(doc)


class TestPaymentEntryControls(UnitTestCase):
	def _pe(self, party_type, refs):
		return frappe._dict(
			party_type=party_type,
			references=[frappe._dict(r) for r in refs],
		)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_employee_pe_against_unverified_claim_is_blocked(self, mock_get_doc):
		mock_get_doc.return_value = frappe._dict(
			doctype="Expense Claim",
			name="EXP-1",
			workflow_state="Approved",
			docstatus=1,
			receipt_review_status="Pending Review",
		)
		doc = self._pe(
			"Employee",
			[{"reference_doctype": "Expense Claim", "reference_name": "EXP-1"}],
		)
		with self.assertRaisesRegex(frappe.ValidationError, "Receipt review must be Verified"):
			validate_payment_entry(doc)

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
		doc = self._pe("Supplier", [{"reference_doctype": "Purchase Invoice", "reference_name": "PINV-1"}])
		validate_payment_entry(doc)

	@patch("volunteering.volunteering.accounting_controls.frappe.get_doc")
	def test_supplier_pe_against_unapproved_pi_blocked(self, mock_get_doc):
		pi = frappe._dict(name="PINV-1", workflow_state="Draft", docstatus=0)
		mock_get_doc.return_value = pi
		doc = self._pe("Supplier", [{"reference_doctype": "Purchase Invoice", "reference_name": "PINV-1"}])
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
