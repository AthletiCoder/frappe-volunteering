import frappe
from frappe.model.document import Document


def normalize_mobile_number(raw_mobile):
    if not raw_mobile:
        return None

    digits = "".join(ch for ch in str(raw_mobile).strip() if ch.isdigit())
    normalized = digits.lstrip("0")
    return normalized or None


def format_mobile_number(raw_mobile, default_country_code="+91"):
    if not raw_mobile:
        return None

    raw = str(raw_mobile).strip()
    country_code = default_country_code
    local_number = raw

    if raw.startswith("+"):
        country_code, local_number = raw.split("-", 1) if "-" in raw else (raw[:3], raw[3:])

    normalized = normalize_mobile_number(local_number)
    if not normalized:
        return raw

    return f"{country_code}-{normalized}"


class Volunteer(Document):
    def validate(self):
        if self.mobile_number:
            self.mobile_number = format_mobile_number(self.mobile_number)