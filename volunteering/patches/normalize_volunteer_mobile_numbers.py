import frappe

from volunteering.volunteering.doctype.volunteer.volunteer import (
    format_mobile_number,
    mobile_lookup_key,
)


def execute():
    seen_keys = set()

    for row in frappe.get_all(
        "Volunteer",
        filters={"mobile_number": ["is", "set"]},
        fields=["name", "mobile_number"],
    ):
        formatted = format_mobile_number(row.mobile_number)
        if not formatted or formatted == row.mobile_number:
            continue

        lookup_key = mobile_lookup_key(formatted)
        if lookup_key in seen_keys:
            frappe.logger("volunteering").warning(
                "Skipping duplicate volunteer mobile normalization for %s (%s)",
                row.name,
                row.mobile_number,
            )
            continue

        frappe.db.set_value(
            "Volunteer",
            row.name,
            "mobile_number",
            formatted,
            update_modified=False,
        )
        seen_keys.add(lookup_key)
