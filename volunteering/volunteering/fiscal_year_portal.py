"""Narrow Fiscal Year setup for Sevamrita System Managers in Home."""

from __future__ import annotations

import re

import frappe
from frappe import _
from frappe.utils import cstr, getdate, nowdate


COMPANY = "Sevamrita Foundation"
YEAR_PATTERN = re.compile(r"20\d{2}-20\d{2}")


def _require_system_manager():
	if frappe.session.user != "Administrator" and "System Manager" not in frappe.get_roles():
		frappe.throw(_("Only a System Manager or Administrator may manage Fiscal Years."), frappe.PermissionError)
	if not frappe.db.exists("Company", COMPANY):
		frappe.throw(_("Set up Sevamrita Foundation before managing Fiscal Years."))


def _is_sevamrita_year(year, companies):
	start = getdate(year.year_start_date)
	end = getdate(year.year_end_date)
	return (
		start.month == 4 and start.day == 1
		and end.month == 3 and end.day == 31 and end.year == start.year + 1
		and (not companies or COMPANY in companies)
	)


def _workspace():
	rows = frappe.get_all(
		"Fiscal Year",
		fields=["name", "year_start_date", "year_end_date", "disabled"],
		order_by="year_start_date desc",
		limit_page_length=0,
	)
	companies = {}
	if rows:
		for row in frappe.get_all(
			"Fiscal Year Company",
			filters={"parent": ["in", [year.name for year in rows]]},
			fields=["parent", "company"],
			limit_page_length=0,
		):
			companies.setdefault(row.parent, set()).add(row.company)
	today = getdate(nowdate())
	multiple_companies = frappe.db.count("Company") > 1
	return {
		"company": COMPANY,
		"years": [
			{
				"name": year.name,
				"start_date": str(year.year_start_date),
				"end_date": str(year.year_end_date),
				"active": not bool(year.disabled),
				"current": getdate(year.year_start_date) <= today <= getdate(year.year_end_date),
				"can_activate": bool(year.disabled) and (bool(companies.get(year.name)) or not multiple_companies),
			}
			for year in rows if _is_sevamrita_year(year, companies.get(year.name))
		],
	}


@frappe.whitelist(methods=["POST"])
def get_fiscal_year_workspace():
	_require_system_manager()
	return _workspace()


@frappe.whitelist(methods=["POST"])
def create_fiscal_year(start_year):
	_require_system_manager()
	raw = cstr(start_year).strip()
	if not re.fullmatch(r"20\d{2}", raw) or int(raw) > 2098:
		frappe.throw(_("Enter a starting year between 2000 and 2098."))
	start = int(raw)
	name = f"{start}-{start + 1}"
	if frappe.db.exists("Fiscal Year", name):
		frappe.throw(_("Fiscal Year {0} already exists. Review its status below.").format(name))
	fiscal_year = frappe.get_doc({
		"doctype": "Fiscal Year",
		"year": name,
		"year_start_date": f"{start}-04-01",
		"year_end_date": f"{start + 1}-03-31",
		"disabled": 0,
		"companies": [{"company": COMPANY}],
	})
	fiscal_year.insert()
	return _workspace()


@frappe.whitelist(methods=["POST"])
def activate_fiscal_year(name):
	_require_system_manager()
	name = cstr(name).strip()
	if not YEAR_PATTERN.fullmatch(name) or not frappe.db.exists("Fiscal Year", name):
		frappe.throw(_("Choose an existing Sevamrita Fiscal Year."))
	fiscal_year = frappe.get_doc("Fiscal Year", name)
	companies = {row.company for row in fiscal_year.companies}
	if not _is_sevamrita_year(fiscal_year, companies):
		frappe.throw(_("This Fiscal Year is not an April–March year available to Sevamrita."))
	if not companies and frappe.db.count("Company") > 1:
		frappe.throw(_("This year applies to every company. Review it in Desk before activating it."))
	if fiscal_year.disabled:
		fiscal_year.disabled = 0
		fiscal_year.save()
	return _workspace()
