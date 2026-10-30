# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

"""Unit + integration tests for De Addiction Pledge APIs (confirm + update)."""

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
TEST_PHOTO_URL = "https://cdn.example.com/pledges/group.jpg"
UPDATED_PHOTO_URL = "https://cdn.example.com/pledges/group_updated.jpg"


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
			city="Mumbai",
		)
		settings = frappe._dict(
			confirmation_template=(
				"ID={pledge_uuid} count={people_count} lang={language} state={state} city={city}"
			)
		)
		msg = pledges_api._build_confirmation_message(doc, settings)
		self.assertEqual(msg, "ID=abc123 count=3 lang=Hindi state=Maharashtra city=Mumbai")

	def test_confirmation_template_falls_back_on_bad_placeholders(self):
		doc = frappe._dict(pledge_uuid="xyz", people_count=1)
		settings = frappe._dict(confirmation_template="Broken {unknown}")
		msg = pledges_api._build_confirmation_message(doc, settings)
		self.assertIn("xyz", msg)
		self.assertIn("1", msg)

	def test_require_positive_int(self):
		self.assertEqual(pledges_api._require_positive_int({"n": 3}, "n"), 3)
		self.assertEqual(pledges_api._require_positive_int({"n": "4"}, "n"), 4)
		with self.assertRaises(pledges_api.PledgeApiError):
			pledges_api._require_positive_int({}, "n")
		with self.assertRaises(pledges_api.PledgeApiError):
			pledges_api._require_positive_int({"n": 0}, "n")
		with self.assertRaises(pledges_api.PledgeApiError):
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

	def _confirm(self, **overrides):
		payload = {
			"mobile_number": unique_mobile("91"),
			"people_count": 5,
			"language": "Hindi",
			"state": "Rajasthan",
			"city": "Jaipur",
			"photo_url": TEST_PHOTO_URL,
		}
		payload.update(overrides)
		return pledges_api.confirm_pledge(**payload)

	def test_confirm_pledge_happy_path(self):
		mobile = unique_mobile("94")
		with self._with_api_key():
			result = self._confirm(
				mobile_number=mobile,
				people_count=5,
				language="Hindi",
				state="Rajasthan",
				city="Jaipur",
			)

		self.assertTrue(result["ok"])
		self.assertTrue(result["pledge_uuid"])
		self.assertEqual(len(result["pledge_uuid"]), PLEDGE_UUID_LENGTH)
		self.assertNotEqual(result["pledge_uuid"][0], "0")
		self.assertTrue(result["name"].startswith("PLDG-"))
		self.assertIn(result["pledge_uuid"], result["confirmation_message"])
		self.assertIn("5", result["confirmation_message"])

		doc = frappe.get_doc("De Addiction Pledge", result["name"])
		self.assertEqual(doc.pledge_uuid, result["pledge_uuid"])
		self.assertEqual(doc.people_count, 5)
		self.assertEqual(doc.language, "Hindi")
		self.assertEqual(doc.state, "Rajasthan")
		self.assertEqual(doc.city, "Jaipur")
		self.assertEqual(doc.photo_url, TEST_PHOTO_URL)
		self.assertEqual(doc.source, "Interakt")
		self.assertTrue(doc.mobile_number)
		self.assertTrue(doc.creation)
		self.assertTrue(doc.raw_payload)

	def test_confirm_pledge_rejects_bad_api_key(self):
		with self._with_api_key("wrong-key"):
			result = self._confirm(mobile_number=unique_mobile("92"))
		self.assertEqual(result, {"ok": False, "message": "Invalid API key"})

	def test_confirm_pledge_rejects_missing_mobile(self):
		with self._with_api_key():
			result = pledges_api.confirm_pledge(
				people_count=1,
				language="Hindi",
				state="Delhi",
				city="Delhi",
				photo_url=TEST_PHOTO_URL,
			)
		self.assertFalse(result["ok"])
		self.assertIn("mobile_number is required", result["message"])

	def test_update_pledge_non_existent_uuid(self):
		with self._with_api_key():
			res = pledges_api.update_pledge(
				uuid="NONEXIST",
				fieldname="photo_url",
				value=UPDATED_PHOTO_URL,
			)
		self.assertFalse(res["ok"])
		self.assertFalse(res["exists"])
		self.assertIn("does not exist", res["message"])
		self.assertEqual(res["pledge_uuid"], "NONEXIST")

	def test_update_pledge_photo_url_happy_path(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge(
				uuid=uuid,
				fieldname="photo_url",
				value=UPDATED_PHOTO_URL,
			)

		self.assertTrue(res["ok"])
		self.assertEqual(res["pledge_uuid"], uuid)
		self.assertEqual(res["fieldname"], "photo_url")
		self.assertEqual(res["value"], UPDATED_PHOTO_URL)

		doc = frappe.get_doc("De Addiction Pledge", created["name"])
		self.assertEqual(doc.photo_url, UPDATED_PHOTO_URL)

	def test_update_pledge_alias_image(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge(
				uuid=uuid,
				fieldname="image",
				value="https://cdn.example.com/new_group.jpg",
			)

		self.assertTrue(res["ok"])
		self.assertEqual(res["fieldname"], "photo_url")
		self.assertEqual(res["value"], "https://cdn.example.com/new_group.jpg")

		doc = frappe.get_doc("De Addiction Pledge", created["name"])
		self.assertEqual(doc.photo_url, "https://cdn.example.com/new_group.jpg")

	def test_update_pledge_rejects_missing_uuid_or_field(self):
		with self._with_api_key():
			res1 = pledges_api.update_pledge(fieldname="photo_url", value=UPDATED_PHOTO_URL)
			self.assertFalse(res1["ok"])
			self.assertIn("uuid is required", res1["message"])

			res2 = pledges_api.update_pledge(uuid="ABC")
			self.assertFalse(res2["ok"])
			self.assertIn("fieldname is required", res2["message"])

	def test_update_pledge_rejects_protected_field(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge(
				uuid=uuid,
				fieldname="pledge_uuid",
				value="NEWUUID1",
			)
			self.assertFalse(res["ok"])
			self.assertIn("cannot be modified", res["message"])

	def test_update_pledge_rejects_non_existent_field(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge(
				uuid=uuid,
				fieldname="unknown_field_xyz",
				value="test",
			)
			self.assertFalse(res["ok"])
			self.assertIn("does not exist", res["message"])

	def test_update_pledge_alias_endpoint(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge_field(
				uuid=uuid,
				fieldname="photo_url",
				value=UPDATED_PHOTO_URL,
			)
			self.assertTrue(res["ok"])
			self.assertEqual(res["pledge_uuid"], uuid)

	def test_update_pledge_direct_kwarg(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge(
				uuid=uuid,
				photo_url=UPDATED_PHOTO_URL,
			)
			self.assertTrue(res["ok"])
			self.assertEqual(res["fieldname"], "photo_url")
			self.assertEqual(res["value"], UPDATED_PHOTO_URL)

	def test_update_pledge_other_fields(self):
		with self._with_api_key():
			created = self._confirm()
			uuid = created["pledge_uuid"]

			res = pledges_api.update_pledge(
				uuid=uuid,
				fieldname="city",
				value="Udaipur",
			)
			self.assertTrue(res["ok"])
			self.assertEqual(res["value"], "Udaipur")

			res2 = pledges_api.update_pledge(
				uuid=uuid,
				fieldname="people_count",
				value=12,
			)
			self.assertTrue(res2["ok"])
			self.assertEqual(res2["value"], 12)


def _ensure_test_pledge_settings():
	"""Minimal settings so get_pledge_settings() / API key auth work in tests."""
	doc = frappe.get_single("De Addiction Pledge Settings")
	doc.api_key = TEST_API_KEY
	doc.confirmation_template = DEFAULT_CONFIRMATION_TEMPLATE
	doc.flags.ignore_permissions = True
	doc.save(ignore_permissions=True)
	frappe.db.commit()
