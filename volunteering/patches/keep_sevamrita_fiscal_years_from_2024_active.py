"""Keep Sevamrita's FY 2024-25 onward open for dated accounting entries.

This one-time migration does not change the default fiscal year or accounting
freeze settings. Later years can be added from the System Manager Home page.
"""

import frappe


COMPANY = "Sevamrita Foundation"
START_YEARS = (2024, 2025, 2026)


def ensure_fiscal_year(start_year):
	name = f"{start_year}-{start_year + 1}"
	start = f"{start_year}-04-01"
	end = f"{start_year + 1}-03-31"

	if frappe.db.exists("Fiscal Year", name):
		fiscal_year = frappe.get_doc("Fiscal Year", name)
		if str(fiscal_year.year_start_date) != start or str(fiscal_year.year_end_date) != end:
			frappe.throw(f"Fiscal Year {name} has unexpected dates; review it before enabling it for {COMPANY}.")
		companies = {row.company for row in fiscal_year.companies}
		if fiscal_year.disabled and frappe.db.count("Company") > 1 and companies != {COMPANY}:
			frappe.throw(
				f"Fiscal Year {name} also affects other companies; review its scope before enabling it."
			)
		changed = False
		if companies and COMPANY not in companies:
			fiscal_year.append("companies", {"company": COMPANY})
			changed = True
		if fiscal_year.disabled:
			fiscal_year.disabled = 0
			changed = True
		if changed:
			fiscal_year.save(ignore_permissions=True)
		return

	frappe.get_doc({
		"doctype": "Fiscal Year",
		"year": name,
		"year_start_date": start,
		"year_end_date": end,
		"disabled": 0,
		"companies": [{"company": COMPANY}],
	}).insert(ignore_permissions=True)


def execute():
	if not frappe.db.exists("Company", COMPANY):
		return
	for start_year in START_YEARS:
		ensure_fiscal_year(start_year)
