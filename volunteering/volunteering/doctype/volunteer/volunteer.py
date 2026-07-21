import frappe
from frappe.model.document import Document


def normalize_mobile_number(raw_mobile):
    if not raw_mobile:
        return None

    digits = "".join(ch for ch in str(raw_mobile).strip() if ch.isdigit())
    normalized = digits.lstrip("0")
    return normalized or None


def format_mobile_number(raw_mobile):
    if not raw_mobile:
        return None

    raw = str(raw_mobile).strip()
    local_part = raw

    if raw.startswith("+"):
        if "-" in raw:
            _, local_part = raw.split("-", 1)
        elif raw.startswith("+91") and len(raw) > 3:
            local_part = raw[3:]
        else:
            local_part = raw[1:]

    normalized = normalize_mobile_number(local_part)
    if not normalized:
        return None

    if len(normalized) == 12 and normalized.startswith("91"):
        normalized = normalized[2:]

    if len(normalized) == 10:
        return f"+91-{normalized}"

    return f"+{normalized}"


def mobile_lookup_key(raw_mobile):
    """Last 10 digits used to match Indian numbers across storage formats."""
    normalized = normalize_mobile_number(raw_mobile)
    if not normalized:
        return None

    if len(normalized) >= 10:
        return normalized[-10:]

    return normalized


def find_volunteer_by_mobile(raw_mobile):
    formatted = format_mobile_number(raw_mobile)
    if not formatted:
        return None

    volunteer_name = frappe.db.get_value(
        "Volunteer", {"mobile_number": formatted}, "name"
    )
    if volunteer_name:
        return volunteer_name

    lookup_key = mobile_lookup_key(formatted)
    if not lookup_key or len(lookup_key) != 10:
        return None

    for row in frappe.get_all(
        "Volunteer",
        filters={"mobile_number": ["is", "set"]},
        fields=["name", "mobile_number"],
    ):
        if mobile_lookup_key(row.mobile_number) == lookup_key:
            return row.name

    return None


def upgrade_volunteer_mobile_number(volunteer_name, formatted_mobile):
    if not volunteer_name or not formatted_mobile:
        return

    stored_mobile = frappe.db.get_value("Volunteer", volunteer_name, "mobile_number")
    if stored_mobile == formatted_mobile:
        return

    frappe.db.set_value(
        "Volunteer",
        volunteer_name,
        "mobile_number",
        formatted_mobile,
        update_modified=False,
    )


class Volunteer(Document):
    def validate(self):
        formatted = format_mobile_number(self.mobile_number)
        if formatted:
            self.mobile_number = formatted

    def on_update(self):
        previous_doc = self.get_doc_before_save()
        if not previous_doc:
            return

        if previous_doc.relationship_manager == self.relationship_manager:
            return

        sync_participation_relationship_managers(self.name, self.relationship_manager)


def sync_participation_relationship_managers(volunteer_name, relationship_manager):
    frappe.db.sql(
        """
        UPDATE `tabParticipation`
        SET relationship_manager = %s
        WHERE volunteer = %s
        """,
        (relationship_manager, volunteer_name),
    )
