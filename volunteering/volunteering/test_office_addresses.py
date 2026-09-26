# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# For license information, please see license.txt

import frappe
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering import invoice_generator as invoices
from volunteering.volunteering import office_addresses as offices
from volunteering.volunteering.accounting_test_utils import (
	get_or_create_department,
	get_or_create_employee,
	get_or_create_user,
)


def address_details(title="_Test Mumbai Office"):
	return {
		"address_title": title,
		"address_type": "Office",
		"address_line1": "12 Test Service Road",
		"address_line2": "Near Test Market",
		"city": "Mumbai",
		"county": "Mumbai Suburban",
		"state": "Maharashtra",
		"country": "India",
		"pincode": "400001",
		"email_id": "office@example.com",
		"phone": "+91 99999 00000",
		"is_primary_address": False,
		"is_shipping_address": False,
		"disabled": False,
	}


class UnitTestOfficeAddresses(UnitTestCase):
	def test_required_fields_and_address_type_are_validated(self):
		for change in (
			{"address_title": ""},
			{"address_line1": ""},
			{"city": ""},
			{"country": ""},
			{"address_type": "Private Residence"},
		):
			with self.subTest(change=change), self.assertRaises(frappe.ValidationError):
				offices._normalise({**address_details(), **change})

	def test_deployable_sevamrita_addresses_match_the_approved_list(self):
		addresses = {row["address_title"]: row for row in offices.SEVAMRITA_OFFICE_ADDRESSES}
		self.assertEqual(
			set(addresses),
			{
				"Registered Office - Kandi",
				"Talegaon Floriculture Park Office",
				"Balewadi Office - Pune",
				"Powai Office - Mumbai",
			},
		)
		self.assertEqual(addresses["Registered Office - Kandi"]["pincode"], "502285")
		self.assertEqual(addresses["Talegaon Floriculture Park Office"]["pincode"], "410507")
		self.assertEqual(addresses["Balewadi Office - Pune"]["pincode"], "411045")
		self.assertEqual(addresses["Powai Office - Mumbai"]["pincode"], "400076")


class IntegrationTestOfficeAddresses(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.set_user("Administrator")
		cls.employee_user = get_or_create_user("office-employee@example.com", ["Employee"])
		cls.manager_user = get_or_create_user("office-manager@example.com", ["Employee", "Accounts Manager"])
		cls.accounts_user = get_or_create_user(
			"office-accounts-user@example.com", ["Employee", "Accounts User"]
		)
		cls.system_user = get_or_create_user(
			"office-system-manager@example.com", ["Employee", "System Manager"]
		)
		department = get_or_create_department("Office Address Test")
		cls.employee = get_or_create_employee(cls.employee_user, department)
		for user in (cls.manager_user, cls.accounts_user, cls.system_user):
			get_or_create_employee(user, department)

	def setUp(self):
		super().setUp()
		frappe.db.savepoint("office_address_test")
		self.addCleanup(self.rollback_test)
		frappe.set_user("Administrator")
		workspace = offices.save_office_address(address_details())
		self.address = next(
			row for row in workspace["addresses"] if row.address_title == "_Test Mumbai Office"
		)

	def tearDown(self):
		frappe.set_user("Administrator")
		super().tearDown()

	def rollback_test(self):
		frappe.db.rollback(save_point="office_address_test")
		frappe.db.value_cache.clear()

	def test_active_employee_can_view_but_cannot_mutate_office_addresses(self):
		frappe.set_user(self.employee_user)
		workspace = offices.get_office_address_workspace()
		self.assertFalse(workspace["can_manage"])
		self.assertIn(self.address.name, {row.name for row in workspace["addresses"]})
		with self.assertRaises(frappe.PermissionError):
			offices.save_office_address(address_details("Employee-created office"))
		with self.assertRaises(frappe.PermissionError):
			offices.delete_office_address(self.address.name, self.address.modified)

		doc = frappe.get_doc("Address", self.address.name)
		doc.address_line1 = "Attempted direct edit"
		with self.assertRaises(frappe.PermissionError):
			doc.save(ignore_permissions=True)

	def test_deployment_seed_is_idempotent_and_company_linked(self):
		frappe.set_user("Administrator")
		first = offices.ensure_sevamrita_office_addresses()
		second = offices.ensure_sevamrita_office_addresses()
		self.assertEqual(first, second)
		self.assertEqual(len(first), 4)

		rows = {
			row.address_title: row
			for row in offices._address_rows(offices.SEVAMRITA_COMPANY, include_disabled=True)
			if row.address_title in {item["address_title"] for item in offices.SEVAMRITA_OFFICE_ADDRESSES}
		}
		self.assertEqual(len(rows), 4)
		self.assertEqual(rows["Registered Office - Kandi"].is_primary_address, 1)
		self.assertEqual(rows["Registered Office - Kandi"].address_line1, "301, Plot No 6, Kandi")
		self.assertEqual(rows["Powai Office - Mumbai"].pincode, "400076")

	def test_invoice_form_lists_addresses_and_server_replaces_forged_party_details(self):
		frappe.set_user(self.employee_user)
		defaults = invoices.get_invoice_generator_defaults()
		choice = next(row for row in defaults["office_addresses"] if row["name"] == self.address.name)
		self.assertEqual(
			choice["party"]["address"], "12 Test Service Road, Near Test Market, Mumbai, Mumbai Suburban"
		)
		self.assertEqual(choice["party"]["state"], "Maharashtra")

		selected = invoices._apply_selected_office_addresses(
			{
				"consignee_address_name": self.address.name,
				"consignee": {"name": "Forged", "address": "Forged address"},
				"buyer_same_as_consignee": False,
				"buyer": {"name": "Forged buyer", "address": "Forged buyer address"},
			},
			self.employee,
		)
		self.assertEqual(selected["consignee"], choice["party"])
		self.assertEqual(selected["buyer"], choice["party"])
		self.assertTrue(selected["buyer_same_as_consignee"])
		with self.assertRaises(frappe.ValidationError):
			invoices._apply_selected_office_addresses(
				{"consignee_address_name": "Not an office", "buyer_same_as_consignee": True},
				self.employee,
			)

	def test_only_accounts_manager_or_administrator_can_manage(self):
		for user in (self.accounts_user, self.system_user):
			frappe.set_user(user)
			self.assertFalse(offices.can_manage_office_addresses())
			with self.assertRaises(frappe.PermissionError):
				offices.save_office_address(address_details(f"Blocked {user}"))

		frappe.set_user(self.manager_user)
		self.assertTrue(offices.can_manage_office_addresses())
		updated = address_details(self.address.address_title)
		updated["address_line1"] = "34 Manager-approved Road"
		workspace = offices.save_office_address(updated, self.address.name, self.address.modified)
		changed = next(row for row in workspace["addresses"] if row.name == self.address.name)
		self.assertEqual(changed.address_line1, "34 Manager-approved Road")
		workspace = offices.delete_office_address(changed.name, changed.modified)
		self.assertNotIn(changed.name, {row.name for row in workspace["addresses"]})

		frappe.set_user("Administrator")
		self.assertTrue(offices.can_manage_office_addresses())

	def test_disabled_office_is_hidden_from_employee_but_visible_to_manager(self):
		frappe.set_user(self.manager_user)
		values = address_details(self.address.address_title)
		values["disabled"] = True
		manager_workspace = offices.save_office_address(values, self.address.name, self.address.modified)
		self.assertIn(self.address.name, {row.name for row in manager_workspace["addresses"]})

		frappe.set_user(self.employee_user)
		employee_workspace = offices.get_office_address_workspace()
		self.assertNotIn(self.address.name, {row.name for row in employee_workspace["addresses"]})

	def test_non_company_addresses_keep_their_existing_permission_model(self):
		frappe.set_user(self.accounts_user)
		doc = frappe.get_doc(
			{
				"doctype": "Address",
				"address_title": "_Test Supplier Address",
				"address_type": "Billing",
				"address_line1": "56 Supplier Road",
				"city": "Mumbai",
				"country": "India",
			}
		)
		doc.insert(ignore_permissions=True)
		self.assertTrue(doc.name)
