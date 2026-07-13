# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Unit + integration tests for Cashfree donation APIs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.api import donations as donations_api
from volunteering.volunteering.api.volunteer_donor import (
	split_full_name,
	upsert_volunteer_for_donation,
)
from volunteering.volunteering.test_utils import unique_mobile


class TestDonationHelpersUnit(UnitTestCase):
	def test_split_full_name(self):
		self.assertEqual(split_full_name("Ada Lovelace"), ("Ada", "Lovelace"))
		self.assertEqual(split_full_name("Madonna"), ("Madonna", ""))
		self.assertEqual(split_full_name("  "), ("Donor", ""))

	def test_idempotency_key_is_uuid_and_stable(self):
		from volunteering.volunteering.api.cashfree_client import idempotency_key_for_order

		key = idempotency_key_for_order("DON-2026-00001")
		self.assertEqual(len(key), 36)
		self.assertEqual(key, idempotency_key_for_order("DON-2026-00001"))
		self.assertNotEqual(key, idempotency_key_for_order("DON-2026-00002"))
		# Valid UUID parse
		import uuid

		uuid.UUID(key)
		self.assertLessEqual(len(key), 64)

	def test_unique_cashfree_order_id(self):
		a = donations_api._unique_cashfree_order_id("DON-2026-00001")
		b = donations_api._unique_cashfree_order_id("DON-2026-00001")
		self.assertTrue(a.startswith("DON-2026-00001-"))
		self.assertNotEqual(a, b)
		self.assertLessEqual(len(a), 50)
		self.assertEqual(len(a.rsplit("-", 1)[1]), 8)

	def test_webhook_signature_valid(self):
		secret = "test_secret"
		timestamp = "1617695238078"
		body = '{"type":"PAYMENT_SUCCESS_WEBHOOK"}'
		message = f"{timestamp}{body}".encode()
		sig = base64.b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).decode()
		self.assertTrue(donations_api._verify_webhook_signature(secret, timestamp, body, sig))

	def test_webhook_signature_rejects_tamper(self):
		secret = "test_secret"
		timestamp = "1617695238078"
		body = '{"type":"PAYMENT_SUCCESS_WEBHOOK"}'
		message = f"{timestamp}{body}".encode()
		sig = base64.b64encode(hmac.new(secret.encode(), message, hashlib.sha256).digest()).decode()
		self.assertFalse(
			donations_api._verify_webhook_signature(secret, timestamp, body + "x", sig)
		)
		self.assertFalse(donations_api._verify_webhook_signature(secret, timestamp, body, "bad"))
		self.assertFalse(donations_api._verify_webhook_signature("", timestamp, body, sig))

	def test_status_token_roundtrip(self):
		token = donations_api._make_status_token("DON-TEST-1")
		self.assertEqual(len(token), 32)
		donations_api._assert_status_token("DON-TEST-1", token)
		with self.assertRaises(frappe.PermissionError):
			donations_api._assert_status_token("DON-TEST-1", "wrong-token")


class IntegrationTestDonationApis(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_test_cashfree_settings()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		# Keep PE off in most tests — accounting can be flaky without full setup
		frappe.db.set_single_value("Cashfree Settings", "create_payment_entry", 0)
		frappe.db.set_single_value("Cashfree Settings", "min_amount", 100)
		frappe.db.set_single_value("Cashfree Settings", "max_amount_per_txn", 500000)
		frappe.db.set_single_value("Cashfree Settings", "max_txns_per_phone_per_hour", 10)

	def _create_pending_donation(self, **overrides):
		mobile = overrides.pop("mobile_number", None) or unique_mobile("93")
		volunteer_name, _ = upsert_volunteer_for_donation(
			full_name=overrides.get("full_name", "API Donor"),
			mobile_number=mobile,
			email=overrides.get("email", f"api-{frappe.generate_hash(length=6)}@example.com"),
		)
		order_id = overrides.pop("cashfree_order_id", None) or f"ORD-{frappe.generate_hash(length=10)}"
		doc = frappe.get_doc(
			{
				"doctype": "Donation",
				"full_name": overrides.get("full_name", "API Donor"),
				"email": overrides.get("email", f"api-{frappe.generate_hash(length=6)}@example.com"),
				"mobile_number": mobile,
				"amount": overrides.get("amount", 250),
				"currency": "INR",
				"status": overrides.get("status", "Pending"),
				"source": "Gateway",
				"want_80g": overrides.get("want_80g", 0),
				"volunteer": volunteer_name,
				"cashfree_order_id": order_id,
				"payment_session_id": "session_test",
			}
		)
		if overrides.get("want_80g"):
			doc.pan = overrides.get("pan", "ABCDE1234F")
			doc.address = overrides.get("address", "Test Address")
		doc.insert(ignore_permissions=True)
		token = donations_api._make_status_token(doc.name)
		doc.db_set("status_token", token, update_modified=False)
		return doc, token

	def test_upsert_volunteer_by_phone_is_idempotent(self):
		mobile = unique_mobile("94")
		name1, matched1 = upsert_volunteer_for_donation(
			full_name="First Donor",
			mobile_number=mobile,
			email=f"first-{frappe.generate_hash(length=5)}@example.com",
		)
		self.assertFalse(matched1)
		name2, matched2 = upsert_volunteer_for_donation(
			full_name="First Donor Updated",
			mobile_number=mobile,
			email=f"second-{frappe.generate_hash(length=5)}@example.com",
			pan="ABCDE1234F",
		)
		self.assertTrue(matched2)
		self.assertEqual(name1, name2)
		volunteer = frappe.get_doc("Volunteer", name1)
		self.assertEqual(volunteer.pan, "ABCDE1234F")

	@patch("volunteering.volunteering.api.donations.cashfree_client.create_order")
	def test_create_donation_and_order_happy_path(self, mock_create):
		mock_create.return_value = {
			"order_id": "ORD-MOCK-1",
			"payment_session_id": "session_abc",
			"order_status": "ACTIVE",
		}
		mobile = unique_mobile("95").replace("+91-", "")
		result = donations_api.create_donation_and_order(
			full_name="Happy Path",
			email=f"happy-{frappe.generate_hash(length=5)}@example.com",
			mobile_number=mobile,
			amount=500,
			want_80g=0,
		)
		self.assertEqual(result["payment_session_id"], "session_abc")
		self.assertTrue(result["donation_id"])
		self.assertTrue(result["status_token"])
		donation = frappe.get_doc("Donation", result["donation_id"])
		self.assertEqual(donation.status, "Pending")
		self.assertEqual(donation.volunteer, result["volunteer"])
		mock_create.assert_called_once()

	@patch("volunteering.volunteering.api.donations.cashfree_client.create_order")
	def test_create_rejects_below_minimum(self, mock_create):
		with self.assertRaises(frappe.ValidationError):
			donations_api.create_donation_and_order(
				full_name="Low Amount",
				email="low@example.com",
				mobile_number=unique_mobile("96").replace("+91-", ""),
				amount=50,
			)
		mock_create.assert_not_called()

	@patch("volunteering.volunteering.api.donations.cashfree_client.create_order")
	def test_create_80g_requires_pan(self, mock_create):
		with self.assertRaises(frappe.ValidationError):
			donations_api.create_donation_and_order(
				full_name="Needs Pan",
				email="pan@example.com",
				mobile_number=unique_mobile("97").replace("+91-", ""),
				amount=200,
				want_80g=1,
				pan="",
				address="Somewhere",
			)
		mock_create.assert_not_called()

	@patch("volunteering.volunteering.api.donations.cashfree_client.create_order")
	def test_fraud_rate_limit_per_phone(self, mock_create):
		def _fake_order(**kwargs):
			return {
				"order_id": f"ORD-{frappe.generate_hash(length=10)}",
				"payment_session_id": f"session_{frappe.generate_hash(length=6)}",
			}

		mock_create.side_effect = _fake_order
		frappe.db.set_single_value("Cashfree Settings", "max_txns_per_phone_per_hour", 2)
		mobile = unique_mobile("81").replace("+91-", "")
		email_base = frappe.generate_hash(length=5)
		for i in range(2):
			donations_api.create_donation_and_order(
				full_name=f"Rate {i}",
				email=f"rate{i}-{email_base}@example.com",
				mobile_number=mobile,
				amount=100,
			)
		with self.assertRaises(frappe.ValidationError):
			donations_api.create_donation_and_order(
				full_name="Rate 3",
				email=f"rate3-{email_base}@example.com",
				mobile_number=mobile,
				amount=100,
			)

	def test_get_donation_status_requires_token(self):
		donation, token = self._create_pending_donation()
		with self.assertRaises(frappe.PermissionError):
			donations_api.get_donation_status(donation_id=donation.name, status_token="nope")
		status = donations_api.get_donation_status(
			donation_id=donation.name, status_token=token
		)
		self.assertEqual(status["status"], "Pending")
		self.assertEqual(status["donation_id"], donation.name)

	@patch("volunteering.volunteering.api.donations.create_payment_entry_for_donation")
	@patch("volunteering.volunteering.api.donations._send_donor_acknowledgement")
	def test_webhook_success_marks_donation(self, mock_mail, mock_pe):
		donation, _token = self._create_pending_donation()
		payload = {
			"type": "PAYMENT_SUCCESS_WEBHOOK",
			"data": {
				"order": {"order_id": donation.cashfree_order_id, "order_status": "PAID"},
				"payment": {"cf_payment_id": "pay_123", "payment_status": "SUCCESS"},
			},
		}
		donations_api._process_webhook_payload(payload)
		donation.reload()
		self.assertEqual(donation.status, "Success")
		self.assertEqual(donation.cf_payment_id, "pay_123")
		mock_pe.assert_called()
		mock_mail.assert_called_with(donation.name)

	@patch("volunteering.volunteering.api.donations.create_payment_entry_for_donation")
	@patch("volunteering.volunteering.api.donations._send_donor_acknowledgement")
	def test_webhook_failed_marks_failed(self, mock_mail, mock_pe):
		donation, _token = self._create_pending_donation()
		payload = {
			"type": "PAYMENT_FAILED_WEBHOOK",
			"data": {
				"order": {"order_id": donation.cashfree_order_id, "order_status": "FAILED"},
				"payment": {"payment_status": "FAILED"},
			},
		}
		donations_api._process_webhook_payload(payload)
		donation.reload()
		self.assertEqual(donation.status, "Failed")
		mock_pe.assert_not_called()

	@patch("volunteering.volunteering.api.donations.create_payment_entry_for_donation")
	@patch("volunteering.volunteering.api.donations._send_donor_acknowledgement")
	def test_webhook_success_is_idempotent(self, mock_mail, mock_pe):
		donation, _token = self._create_pending_donation()
		donation.db_set("payment_entry", "PE-ALREADY", update_modified=False)
		donation.db_set("status", "Success", update_modified=False)
		donation.reload()

		payload = {
			"type": "PAYMENT_SUCCESS_WEBHOOK",
			"data": {
				"order": {"order_id": donation.cashfree_order_id, "order_status": "PAID"},
				"payment": {"cf_payment_id": "pay_dup", "payment_status": "SUCCESS"},
			},
		}
		donations_api._process_webhook_payload(payload)
		donations_api._process_webhook_payload(payload)
		donation.reload()
		self.assertEqual(donation.status, "Success")
		# Early return when already Success + payment_entry — PE not created again
		mock_pe.assert_not_called()

	@patch("volunteering.volunteering.api.donations.cashfree_client.get_order")
	@patch("volunteering.volunteering.api.donations.create_payment_entry_for_donation")
	@patch("volunteering.volunteering.api.donations._send_donor_acknowledgement")
	def test_reconcile_marks_paid_from_get_order(self, mock_mail, mock_pe, mock_get):
		donation, _token = self._create_pending_donation(status="Pending")
		mock_get.return_value = {"order_status": "PAID", "order_id": donation.cashfree_order_id}
		status = donations_api.mark_donation_from_order_status(donation.name)
		self.assertEqual(status, "Success")
		donation.reload()
		self.assertEqual(donation.status, "Success")

	def test_cashfree_webhook_rejects_bad_signature(self):
		raw = json.dumps({"type": "PAYMENT_SUCCESS_WEBHOOK", "data": {}})
		frappe.local.request = MagicMock()
		frappe.local.request.get_data = MagicMock(return_value=raw)
		# Headers via frappe.get_request_header
		with patch(
			"volunteering.volunteering.api.donations.frappe.get_request_header",
			side_effect=lambda k: {
				"x-webhook-timestamp": "123",
				"x-webhook-signature": "invalid",
			}.get(k),
		):
			with self.assertRaises(frappe.AuthenticationError):
				donations_api.cashfree_webhook()


def _ensure_test_cashfree_settings():
	"""Minimal Cashfree Settings so get_cashfree_settings() works in tests."""
	doc = frappe.get_single("Cashfree Settings")
	doc.environment = "sandbox"
	doc.app_id = doc.app_id or "TEST_APP_ID"
	if not doc.get_password("secret_key", raise_exception=False):
		doc.secret_key = "test_secret_key_for_unit_tests"
	if not doc.get_password("webhook_secret", raise_exception=False):
		doc.webhook_secret = "test_secret_key_for_unit_tests"
	doc.min_amount = doc.min_amount or 100
	doc.max_amount_per_txn = doc.max_amount_per_txn or 500000
	doc.max_txns_per_phone_per_hour = doc.max_txns_per_phone_per_hour or 10
	doc.create_payment_entry = 0
	if not doc.company:
		doc.company = frappe.db.get_value("Company", {}, "name")
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
