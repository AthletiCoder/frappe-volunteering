# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from volunteering import hooks
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.doctype.volunteer.volunteer import (
    find_volunteer_by_mobile,
    format_mobile_number,
    mobile_lookup_key,
)
from volunteering.volunteering.test_utils import unique_mobile


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = ["User", "Company"]



class TestVolunteerMobileHelpers(UnitTestCase):
    def test_mobile_lookup_key_uses_last_ten_digits(self):
        self.assertEqual(mobile_lookup_key("+91-9876543210"), "9876543210")
        self.assertEqual(mobile_lookup_key("919876543210"), "9876543210")
        self.assertEqual(mobile_lookup_key("09876543210"), "9876543210")

    def test_format_mobile_number_normalizes_indian_numbers(self):
        self.assertEqual(format_mobile_number("09876543210"), "+91-9876543210")
        self.assertEqual(format_mobile_number("+919876543210"), "+91-9876543210")


class IntegrationTestVolunteer(IntegrationTestCase):
    """
    Integration tests for Volunteer.
    Use this class for testing interactions between multiple components.
    """

    def test_permission_query_condition_hooks_are_importable(self):
        for path in hooks.permission_query_conditions.values():
            self.assertTrue(callable(frappe.get_attr(path)))

    def test_mobile_number_is_normalized_on_save(self):
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Normalize Phone",
                "mobile_number": "0009876543210",
            }
        ).insert(ignore_permissions=True)

        self.assertEqual(volunteer.mobile_number, "+91-9876543210")

    def test_find_volunteer_by_mobile_matches_legacy_bare_digits(self):
        formatted_phone = unique_mobile("95")
        bare_digits = formatted_phone.replace("+91-", "")

        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Legacy Lookup",
                "mobile_number": formatted_phone,
            }
        ).insert(ignore_permissions=True)
        frappe.db.set_value(
            "Volunteer",
            volunteer.name,
            "mobile_number",
            bare_digits,
            update_modified=False,
        )

        self.assertEqual(find_volunteer_by_mobile(formatted_phone), volunteer.name)
