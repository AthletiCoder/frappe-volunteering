# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from frappe.utils import nowdate
from frappe.tests import IntegrationTestCase

from volunteering.volunteering.doctype.participation.participation import (
    check_event_registration,
    is_registered_for_event,
)
from volunteering.volunteering.test_utils import make_test_phone, unique_mobile


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = ["Volunteer", "NGO Event", "Project", "Company", "User"]



class IntegrationTestParticipation(IntegrationTestCase):
    """
    Integration tests for Participation.
    Use this class for testing interactions between multiple components.
    """

    def create_event(self):
        return frappe.get_doc(
            {
                "doctype": "NGO Event",
                "title": f"Event-{frappe.generate_hash(length=8)}",
                "startdate": nowdate(),
                "enddate": nowdate(),
            }
        ).insert(ignore_permissions=True)

    def test_before_insert_links_volunteer_from_temp_phone(self):
        event = self.create_event()

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "Test Volunteer",
                "temp_phone": make_test_phone(),
                "temp_email": f"vol-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertTrue(participation.volunteer)
        self.assertTrue(frappe.db.exists("Volunteer", participation.volunteer))

    def test_before_insert_requires_volunteer_without_phone(self):
        event = self.create_event()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Participation",
                    "event": event.name,
                    "temp_full_name": "No Phone Volunteer",
                }
            ).insert(ignore_permissions=True)

    def test_before_insert_links_legacy_bare_digit_volunteer(self):
        event = self.create_event()
        formatted_phone = unique_mobile("96")
        bare_digits = formatted_phone.replace("+91-", "")

        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Legacy Volunteer",
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

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "Returning Volunteer",
                "temp_phone": formatted_phone,
                "temp_email": f"legacy-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertEqual(participation.volunteer, volunteer.name)
        self.assertEqual(
            frappe.db.get_value("Volunteer", volunteer.name, "mobile_number"),
            formatted_phone,
        )

    def test_before_insert_links_existing_volunteer_with_leading_zero_phone(self):
        event = self.create_event()
        base_phone = make_test_phone("9876543210")

        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Existing Volunteer",
                "mobile_number": base_phone,
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "Temp Volunteer",
                "temp_phone": base_phone.replace("+91-", "0"),
                "temp_email": f"lead-zero-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertEqual(participation.volunteer, volunteer.name)
        self.assertEqual(participation.temp_phone, base_phone)

    def test_before_insert_rejects_all_zero_phone(self):
        event = self.create_event()

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Participation",
                    "event": event.name,
                    "temp_full_name": "All Zero Phone",
                    "temp_phone": "+91-000000",
                }
            ).insert(ignore_permissions=True)

    def test_kits_delivered_update_without_rating_clears_volunteer_rollup(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Kits Volunteer",
                "mobile_number": unique_mobile("97"),
            }
        ).insert(ignore_permissions=True)

        participation = frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

        participation.kits_delivered = 5
        participation.save(ignore_permissions=True)

        volunteer.reload()
        self.assertEqual(volunteer.effective_rating, 0)
        self.assertEqual(volunteer.rating_sample_size, 0)
        self.assertEqual(participation.effective_rating, 0)

    def test_check_event_registration_returns_false_for_unknown_phone(self):
        event = self.create_event()
        phone = make_test_phone()

        self.assertFalse(is_registered_for_event(phone, event.name))
        self.assertEqual(
            check_event_registration(phone, event.name),
            {"registered": False},
        )

    def test_duplicate_registration_is_blocked(self):
        event = self.create_event()
        phone = make_test_phone()

        frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "temp_full_name": "First Volunteer",
                "temp_phone": phone,
                "temp_email": f"dup-{frappe.generate_hash(length=6)}@example.com",
            }
        ).insert(ignore_permissions=True)

        self.assertTrue(is_registered_for_event(phone, event.name))
        self.assertEqual(
            check_event_registration(phone, event.name),
            {"registered": True},
        )

        with self.assertRaises(frappe.ValidationError):
            frappe.get_doc(
                {
                    "doctype": "Participation",
                    "event": event.name,
                    "temp_full_name": "Duplicate Volunteer",
                    "temp_phone": phone,
                    "temp_email": f"dup2-{frappe.generate_hash(length=6)}@example.com",
                }
            ).insert(ignore_permissions=True)
