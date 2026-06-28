# Copyright (c) 2026, Vadiraj Tirtha Das and Contributors
# See license.txt

import frappe
from volunteering import hooks
from frappe.tests import IntegrationTestCase, UnitTestCase

from volunteering.volunteering.doctype.volunteer.volunteer import (
    find_volunteer_by_mobile,
    format_mobile_number,
    mobile_lookup_key,
    sync_participation_relationship_managers,
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
                "mobile_number": "+91-0009876543210",
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

    def create_event(self):
        from frappe.utils import nowdate

        return frappe.get_doc(
            {
                "doctype": "NGO Event",
                "title": f"VolunteerEvent-{frappe.generate_hash(length=8)}",
                "startdate": nowdate(),
                "enddate": nowdate(),
            }
        ).insert(ignore_permissions=True)

    def create_participation(self, event, volunteer):
        return frappe.get_doc(
            {
                "doctype": "Participation",
                "event": event.name,
                "volunteer": volunteer.name,
            }
        ).insert(ignore_permissions=True)

    def test_volunteer_rm_change_propagates_to_participations(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "RM Sync Volunteer",
                "mobile_number": unique_mobile("93"),
                "relationship_manager": frappe.session.user,
            }
        ).insert(ignore_permissions=True)
        participation_one = self.create_participation(event, volunteer)
        participation_two = self.create_participation(event, volunteer)

        volunteer.relationship_manager = None
        volunteer.save(ignore_permissions=True)

        participation_one.reload()
        participation_two.reload()
        self.assertFalse(participation_one.relationship_manager)
        self.assertFalse(participation_two.relationship_manager)

    def test_volunteer_rm_change_does_not_affect_other_volunteers(self):
        event = self.create_event()
        volunteer_a = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Volunteer A",
                "mobile_number": unique_mobile("92"),
                "relationship_manager": frappe.session.user,
            }
        ).insert(ignore_permissions=True)
        volunteer_b = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Volunteer B",
                "mobile_number": unique_mobile("91"),
            }
        ).insert(ignore_permissions=True)
        participation_a = self.create_participation(event, volunteer_a)
        participation_b = self.create_participation(event, volunteer_b)

        volunteer_a.relationship_manager = None
        volunteer_a.save(ignore_permissions=True)

        participation_a.reload()
        participation_b.reload()
        self.assertFalse(participation_a.relationship_manager)
        self.assertFalse(participation_b.relationship_manager)

    def test_volunteer_save_without_rm_change_skips_participation_update(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Stable RM Volunteer",
                "mobile_number": unique_mobile("90"),
                "relationship_manager": frappe.session.user,
            }
        ).insert(ignore_permissions=True)
        participation = self.create_participation(event, volunteer)

        volunteer.first_name = "Renamed Volunteer"
        volunteer.save(ignore_permissions=True)

        participation.reload()
        self.assertEqual(participation.relationship_manager, frappe.session.user)

    def test_sync_participation_relationship_managers_helper(self):
        event = self.create_event()
        volunteer = frappe.get_doc(
            {
                "doctype": "Volunteer",
                "first_name": "Helper Volunteer",
                "mobile_number": unique_mobile("89"),
            }
        ).insert(ignore_permissions=True)
        participation = self.create_participation(event, volunteer)

        sync_participation_relationship_managers(volunteer.name, frappe.session.user)

        self.assertEqual(
            frappe.db.get_value("Participation", participation.name, "relationship_manager"),
            frappe.session.user,
        )
