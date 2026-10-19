# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Unit + integration tests for De Addiction Pledge Interakt APIs."""

from __future__ import annotations

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.api import pledges as pledges_api
from volunteering.volunteering.doctype.de_addiction_pledge.de_addiction_pledge import (
	PLEDGE_UUID_ALPHABET,
	PLEDGE_UUID_LENGTH,
	generate_pledge_uuid,
)
from volunteering.volunteering.doctype.de_addiction_pledge_settings.de_addiction_pledge_settings import (
	DEFAULT_CONFIRMATION_TEMPLATE,
)
from volunteering.volunteering.test_utils import unique_mobile

TEST_API_KEY = "test-pledge-api-key"


class TestPledgeHelpersUnit(UnitTestCase):
	@patch(
		"volunteering.volunteering.doctype.de_addiction_pledge.de_addiction_pledge.frappe.db.exists",
		return_value=False,
	)
	def test_generate_pledge_uuid_format(self, _mock_exists):
		code = generate_pledge_uuid()
		self.assertEqual(len(code), PLEDGE_UUID_LENGTH)
		self.assertNotEqual(code[0], "0")
		self.assertTrue(all(ch in PLEDGE_UUID_ALPHABET for ch in code))
		self.assertEqual(code, code.upper())

	def test_confirmation_template_placeholders(self):
		doc = frappe._dict(
			pledge_uuid="abc123",
			people_count=3,
			mobile_number="+91-9876543210",
			language="Hindi",
			state="Maharashtra",
		)
		settings = frappe._dict(
			confirmation_template=(
				"ID={pledge_uuid} count={people_count} lang={language} state={state}"
			)
		)
		msg = pledges_api._build_confirmation_message(doc, settings)
		self.assertEqual(msg, "ID=abc123 count=3 lang=Hindi state=Maharashtra")

	def test_confirmation_template_falls_back_on_bad_placeholders(self):
		doc = frappe._dict(pledge_uuid="xyz", people_count=1)
		settings = frappe._dict(confirmation_template="Broken {unknown}")
		msg = pledges_api._build_confirmation_message(doc, settings)
		self.assertIn("xyz", msg)
		self.assertIn("1", msg)

	def test_require_positive_int(self):
		self.assertEqual(pledges_api._require_positive_int({"n": 3}, "n"), 3)
		self.assertEqual(pledges_api._require_positive_int({"n": "4"}, "n"), 4)
		with self.assertRaises(frappe.ValidationError):
			pledges_api._require_positive_int({}, "n")
		with self.assertRaises(frappe.ValidationError):
			pledges_api._require_positive_int({"n": 0}, "n")
		with self.assertRaises(frappe.ValidationError):
			pledges_api._require_positive_int({"n": "x"}, "n")


class IntegrationTestPledgeApis(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_ensure_test_pledge_settings()

	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		_ensure_test_pledge_settings()

	def _with_api_key(self, key=TEST_API_KEY):
		return patch(
			"volunteering.volunteering.api.pledges.frappe.get_request_header",
			side_effect=lambda h: key if h == pledges_api.API_KEY_HEADER else None,
		)

	def test_start_pledge_creates_draft(self):
		mobile = unique_mobile("91")
		with self._with_api_key():
			result = pledges_api.start_pledge(mobile_number=mobile)

		self.assertTrue(result["pledge_uuid"])
		self.assertEqual(len(result["pledge_uuid"]), PLEDGE_UUID_LENGTH)
		self.assertNotEqual(result["pledge_uuid"][0], "0")
		self.assertTrue(result["name"].startswith("PLDG-"))
		self.assertEqual(result["status"], "Draft")

		doc = frappe.get_doc("De Addiction Pledge", result["name"])
		self.assertEqual(doc.pledge_uuid, result["pledge_uuid"])
		self.assertEqual(doc.status, "Draft")
		self.assertEqual(doc.source, "Interakt")
		self.assertTrue(doc.mobile_number)
		self.assertTrue(doc.started_on)
		self.assertFalse(doc.completed_on)

	def test_start_pledge_rejects_bad_api_key(self):
		with self._with_api_key("wrong-key"):
			with self.assertRaises(frappe.AuthenticationError):
				pledges_api.start_pledge(mobile_number=unique_mobile("92"))

	def test_start_pledge_rejects_missing_mobile(self):
		with self._with_api_key():
			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.start_pledge()
			self.assertIn("mobile_number is required", str(ctx.exception))

	def test_start_pledge_rejects_empty_mobile(self):
		with self._with_api_key():
			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.start_pledge(mobile_number="")
			self.assertIn("mobile_number is required", str(ctx.exception))

	def test_start_pledge_rejects_invalid_mobile(self):
		with self._with_api_key():
			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.start_pledge(mobile_number="123")
			self.assertIn("mobile_number is invalid", str(ctx.exception))

	def test_duplicate_phone_creates_two_pledges(self):
		mobile = unique_mobile("93")
		with self._with_api_key():
			a = pledges_api.start_pledge(mobile_number=mobile)
			b = pledges_api.start_pledge(mobile_number=mobile)

		self.assertNotEqual(a["pledge_uuid"], b["pledge_uuid"])
		self.assertNotEqual(a["name"], b["name"])
		formatted = frappe.db.get_value("De Addiction Pledge", a["name"], "mobile_number")
		self.assertEqual(
			frappe.db.count("De Addiction Pledge", {"mobile_number": formatted}),
			2,
		)

	def test_complete_pledge_happy_path(self):
		mobile = unique_mobile("94")
		with self._with_api_key():
			started = pledges_api.start_pledge(mobile_number=mobile)
			result = pledges_api.complete_pledge(
				pledge_uuid=started["pledge_uuid"],
				people_count=5,
				language="Hindi",
				state="Rajasthan",
			)

		self.assertEqual(result["pledge_uuid"], started["pledge_uuid"])
		self.assertEqual(result["status"], "Completed")
		self.assertIn(started["pledge_uuid"], result["confirmation_message"])
		self.assertIn("5", result["confirmation_message"])

		doc = frappe.get_doc("De Addiction Pledge", result["name"])
		self.assertEqual(doc.status, "Completed")
		self.assertEqual(doc.people_count, 5)
		self.assertEqual(doc.language, "Hindi")
		self.assertEqual(doc.state, "Rajasthan")
		self.assertEqual(doc.confirmation_sent, 1)
		self.assertTrue(doc.started_on)
		self.assertTrue(doc.completed_on)
		self.assertTrue(doc.raw_payload)

	def test_complete_pledge_missing_uuid(self):
		with self._with_api_key():
			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.complete_pledge(
					people_count=1, language="Hindi", state="Delhi"
				)
			self.assertIn("pledge_uuid is required", str(ctx.exception))

	def test_complete_pledge_unknown_uuid(self):
		with self._with_api_key():
			with self.assertRaises(frappe.DoesNotExistError) as ctx:
				pledges_api.complete_pledge(
					pledge_uuid="does-not-exist",
					people_count=1,
					language="Hindi",
					state="Delhi",
				)
			self.assertIn("No pledge found", str(ctx.exception))

	def test_complete_pledge_requires_people_count_language_state(self):
		mobile = unique_mobile("96")
		with self._with_api_key():
			started = pledges_api.start_pledge(mobile_number=mobile)
			uuid = started["pledge_uuid"]

			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.complete_pledge(
					pledge_uuid=uuid, language="Hindi", state="Delhi"
				)
			self.assertIn("people_count is required", str(ctx.exception))

			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.complete_pledge(
					pledge_uuid=uuid, people_count=0, language="Hindi", state="Delhi"
				)
			self.assertIn("whole number of 1 or more", str(ctx.exception))

			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.complete_pledge(
					pledge_uuid=uuid, people_count="abc", language="Hindi", state="Delhi"
				)
			self.assertIn("whole number of 1 or more", str(ctx.exception))

			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.complete_pledge(
					pledge_uuid=uuid, people_count=2, language="", state="Delhi"
				)
			self.assertIn("language is required", str(ctx.exception))

			with self.assertRaises(frappe.ValidationError) as ctx:
				pledges_api.complete_pledge(
					pledge_uuid=uuid, people_count=2, language="Hindi", state="  "
				)
			self.assertIn("state is required", str(ctx.exception))

	def test_complete_pledge_retry_last_write_wins(self):
		mobile = unique_mobile("95")
		with self._with_api_key():
			started = pledges_api.start_pledge(mobile_number=mobile)
			first = pledges_api.complete_pledge(
				pledge_uuid=started["pledge_uuid"],
				people_count=2,
				language="English",
				state="Delhi",
			)
			second = pledges_api.complete_pledge(
				pledge_uuid=started["pledge_uuid"],
				people_count=7,
				language="Marathi",
				state="Maharashtra",
			)

		self.assertEqual(first["status"], "Completed")
		self.assertEqual(second["status"], "Completed")
		self.assertIn("7", second["confirmation_message"])

		doc = frappe.get_doc("De Addiction Pledge", started["name"])
		self.assertEqual(doc.people_count, 7)
		self.assertEqual(doc.language, "Marathi")
		self.assertEqual(doc.state, "Maharashtra")
		self.assertEqual(doc.confirmation_sent, 1)


def _ensure_test_pledge_settings():
	"""Minimal settings so get_pledge_settings() / API key auth work in tests."""
	doc = frappe.get_single("De Addiction Pledge Settings")
	doc.api_key = TEST_API_KEY
	doc.confirmation_template = DEFAULT_CONFIRMATION_TEMPLATE
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
