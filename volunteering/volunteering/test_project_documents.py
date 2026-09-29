# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering import project_documents as docs
from volunteering.volunteering.accounting_test_utils import get_or_create_user
from volunteering.volunteering.employee_bank_accounts import REQUEST_DOCTYPE


class UnitTestProjectDocumentsPermission(UnitTestCase):
	def test_non_scoped_file_does_not_deny_create(self):
		file = frappe._dict(
			attached_to_doctype="Web Form",
			attached_to_name="event-registration-form",
			is_private=0,
		)
		self.assertTrue(docs.has_permission(file, ptype="create"))

	def test_scoped_project_file_denies_create(self):
		file = frappe._dict(attached_to_doctype="Project", attached_to_name="PROJ-1", is_private=1)
		self.assertFalse(docs.has_permission(file, ptype="create"))

	def test_scoped_bank_file_denies_create(self):
		file = frappe._dict(
			attached_to_doctype=REQUEST_DOCTYPE,
			attached_to_name="EBAR-1",
			is_private=1,
		)
		self.assertFalse(docs.has_permission(file, ptype="create"))


class IntegrationTestProjectDocumentsPermission(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		with patch("frappe.utils.global_search.sync_value_in_queue"):
			cls.uploader = get_or_create_user(
				"file-banner-uploader@example.com",
				["System Manager"],
				first_name="BannerUploader",
			)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def test_public_web_form_banner_file_create_is_allowed(self):
		frappe.set_user(self.uploader)
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "banner-test.png",
				"is_private": 0,
				"attached_to_doctype": "Web Form",
				"attached_to_name": "event-registration-form",
				"folder": "Home",
			}
		)
		file.owner = self.uploader
		self.assertTrue(frappe.has_permission("File", "create", doc=file, user=self.uploader))

	def test_scoped_project_file_create_is_denied(self):
		frappe.set_user(self.uploader)
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "evidence.pdf",
				"is_private": 1,
				"attached_to_doctype": "Project",
				"attached_to_name": "PROJ-TEST",
				"folder": "Home",
			}
		)
		file.owner = self.uploader
		self.assertFalse(frappe.has_permission("File", "create", doc=file, user=self.uploader))
