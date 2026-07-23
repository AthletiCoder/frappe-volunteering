# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import UnitTestCase

from volunteering.volunteering.approval_routing import (
	find_first_approver,
)
from volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings import (
	designation_can_approve,
)
from volunteering.volunteering.payout_provider import ManualPayoutProvider, get_payout_provider


def _settings_with_limits():
	return frappe._dict(
		use_designation_approval=1,
		tier_1_limit=2000,
		tier_2_limit=10000,
		designation_limits=[
			frappe._dict(
				designation="Manager", max_approve_amount=2000, max_advance_amount=5000
			),
			frappe._dict(
				designation="CEO", max_approve_amount=50000, max_advance_amount=50000
			),
			frappe._dict(
				designation="Board of Directors", max_approve_amount=0, max_advance_amount=0
			),
		],
	)


class TestDesignationApproval(UnitTestCase):
	@patch(
		"volunteering.volunteering.doctype.volunteering_accounting_settings.volunteering_accounting_settings.get_accounting_settings"
	)
	def test_designation_can_approve_respects_limit(self, mock_settings):
		mock_settings.return_value = _settings_with_limits()
		self.assertTrue(designation_can_approve("Manager", 1500))
		self.assertFalse(designation_can_approve("Manager", 5000))
		self.assertTrue(designation_can_approve("Board of Directors", 999999))

	@patch("volunteering.volunteering.approval_routing.get_accounting_settings")
	@patch("volunteering.volunteering.approval_routing.frappe.db.get_value")
	def test_find_first_approver_skips_low_limit_manager(self, mock_get_value, mock_settings):
		mock_settings.return_value = _settings_with_limits()

		def _get_value(doctype, name, fieldname=None, *args, **kwargs):
			if doctype == "Employee" and name == "EMP" and fieldname == "reports_to":
				return "MGR"
			if doctype == "Employee" and name == "MGR" and fieldname == "reports_to":
				return "CEO_EMP"
			if doctype == "Employee" and name == "MGR" and fieldname == "user_id":
				return "mgr@example.com"
			if doctype == "Employee" and name == "MGR" and fieldname == "designation":
				return "Manager"
			if doctype == "Employee" and name == "CEO_EMP" and fieldname == "user_id":
				return "ceo@example.com"
			if doctype == "Employee" and name == "CEO_EMP" and fieldname == "designation":
				return "CEO"
			if doctype == "Employee" and name == "CEO_EMP" and fieldname == "reports_to":
				return None
			return None

		mock_get_value.side_effect = _get_value
		self.assertEqual(find_first_approver("EMP", 5000), "ceo@example.com")
		self.assertEqual(find_first_approver("EMP", 1500), "mgr@example.com")

	def test_manual_payout_provider_default(self):
		provider = get_payout_provider()
		self.assertIsInstance(provider, ManualPayoutProvider)
		result = provider.create_payout("PE-0001")
		self.assertEqual(result["provider"], "manual")


class TestLegacyTierStillWork(UnitTestCase):
	@patch("volunteering.volunteering.approval_routing.get_accounting_settings")
	def test_legacy_amount_tiers(self, mock_settings):
		from volunteering.volunteering.approval_routing import get_amount_approval_level

		mock_settings.return_value = frappe._dict(
			use_designation_approval=0,
			tier_1_limit=2000,
			tier_2_limit=10000,
		)
		low = frappe._dict(doctype="Expense Claim", total_claimed_amount=1500)
		self.assertEqual(get_amount_approval_level(low), 1)


class TestApproverActionFlags(UnitTestCase):
	def _mock_doc(self, mock_get_doc):
		doc = MagicMock()
		doc.name = "EC-1"
		doc.doctype = "Expense Claim"
		doc.workflow_state = "Pending Approval"
		doc.pending_approver = frappe.session.user
		doc.get = lambda key, default=None: getattr(doc, key, default)
		mock_get_doc.return_value = doc
		return doc

	@patch("volunteering.volunteering.approval_routing.user_can_approve_amount")
	@patch("volunteering.volunteering.approval_routing.use_designation_approval")
	@patch("volunteering.volunteering.approval_routing.get_document_amount")
	@patch("volunteering.volunteering.approval_routing.frappe.get_doc")
	def test_escalate_blocked_when_under_limit(
		self, mock_get_doc, mock_amount, mock_use_desig, mock_can_approve
	):
		from volunteering.volunteering.approval_routing import escalate_document

		self._mock_doc(mock_get_doc)
		mock_amount.return_value = 1000
		mock_use_desig.return_value = True
		mock_can_approve.return_value = True
		with self.assertRaises(frappe.ValidationError):
			escalate_document("Expense Claim", "EC-1", "need higher")

	@patch("volunteering.volunteering.approval_routing.user_can_approve_amount")
	@patch("volunteering.volunteering.approval_routing.use_designation_approval")
	@patch("volunteering.volunteering.approval_routing.get_document_amount")
	@patch("volunteering.volunteering.approval_routing.frappe.get_doc")
	def test_approver_flags_escalate_only_when_over_limit(
		self, mock_get_doc, mock_amount, mock_use_desig, mock_can_approve
	):
		from volunteering.volunteering.approval_routing import get_approver_action_flags

		self._mock_doc(mock_get_doc)
		mock_amount.return_value = 5000
		mock_use_desig.return_value = True
		mock_can_approve.return_value = False
		flags = get_approver_action_flags("Expense Claim", "EC-1")
		self.assertTrue(flags["can_escalate"])
		self.assertFalse(flags["can_approve"])
		self.assertTrue(flags["can_reject"])

		mock_can_approve.return_value = True
		flags = get_approver_action_flags("Expense Claim", "EC-1")
		self.assertFalse(flags["can_escalate"])
		self.assertTrue(flags["can_approve"])
