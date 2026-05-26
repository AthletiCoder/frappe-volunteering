import frappe
from frappe.model.document import Document


def normalize_mobile_number(raw_mobile):
    if not raw_mobile:
        return None

    digits = "".join(ch for ch in str(raw_mobile).strip() if ch.isdigit())
    normalized = digits.lstrip("0")
    return normalized or None


class Volunteer(Document):
    pass