# Copyright (c) 2026, Vadiraj Tirtha Das and contributors
# Temporary debug probe — remove after verification

from __future__ import annotations

import json
import time

import frappe


LOG = "/Users/varunkumar/Documents/coding/erp/erpnext/frappe-bench/.cursor/debug-4c4245.log"


def _log(hypothesis_id, location, message, data, run_id="pre-verify"):
	with open(LOG, "a", encoding="utf-8") as f:
		f.write(
			json.dumps(
				{
					"sessionId": "4c4245",
					"hypothesisId": hypothesis_id,
					"location": location,
					"message": message,
					"data": data,
					"timestamp": int(time.time() * 1000),
					"runId": run_id,
				}
			)
			+ "\n"
		)


def probe(user="nived@sevamrita.org"):
	from volunteering.volunteering.volunteering_access import (
		user_has_volunteering_ops_access,
		volunteer_email_for_user,
	)
	from volunteering.volunteering import (
		participation_permissions,
		reciprocation_permissions,
		volunteer_permissions,
	)

	frappe.set_user(user)
	roles = frappe.get_roles(user)
	ops = user_has_volunteering_ops_access(user)
	email = volunteer_email_for_user(user)
	vcond = volunteer_permissions.get_permission_query_conditions(user)
	pcond = participation_permissions.get_permission_query_conditions(user)
	rcond = reciprocation_permissions.get_permission_query_conditions(user)

	_log(
		"H2",
		"debug_number_card.probe",
		"access snapshot",
		{
			"user": user,
			"ops": ops,
			"email": email,
			"has_member": "NGO Member" in roles,
			"has_coordinator": "NGO Coordinator" in roles,
			"vcond": vcond,
			"pcond": pcond,
			"rcond": rcond,
			"roles": sorted(roles),
		},
	)

	for doctype, hyp in (("Participation", "H2"), ("Reciprocation", "H3"), ("Volunteer", "H1")):
		try:
			# apply permission query like list view
			cond = frappe.get_attr(
				frappe.get_hooks("permission_query_conditions").get(doctype)
				or frappe.get_hooks("permission_query_conditions")[doctype]
			) if False else None
		except Exception:
			cond = None
		try:
			n = frappe.db.count(doctype)
			# also count with explicit filter via get_list
			rows = frappe.get_list(doctype, fields=["name"], limit_page_length=5)
			_log(hyp, f"probe.count.{doctype}", "ok", {"db_count": n, "list_len": len(rows)})
		except Exception as e:
			_log(hyp, f"probe.count.{doctype}", "fail", {"err": str(e)[:400]})

	# Number cards used on Volunteering workspace
	from frappe.desk.doctype.number_card.number_card import get_result

	ws = frappe.get_doc("Workspace", "Volunteering") if frappe.db.exists("Workspace", "Volunteering") else None
	card_names = []
	if ws:
		for row in ws.as_dict().get("number_cards") or []:
			if row.get("number_card_name"):
				card_names.append(row["number_card_name"])
		# Frappe 16 may store in content JSON
		content = ws.content
		if isinstance(content, str):
			try:
				content = json.loads(content)
			except Exception:
				content = []
		for block in content or []:
			if isinstance(block, dict) and block.get("type") == "number_card":
				data = block.get("data") or {}
				name = data.get("number_card_name") or data.get("card_name")
				if name:
					card_names.append(name)

	card_names = list(dict.fromkeys(card_names))
	_log("H4", "probe.workspace_cards", "card names", {"names": card_names})

	for name in card_names:
		try:
			doc = frappe.get_cached_doc("Number Card", name)
			filters = doc.filters_json
			if isinstance(filters, str):
				filters = json.loads(filters) if filters else []
			val = get_result(doc, filters)
			_log(
				"H4",
				"probe.card_result",
				"ok",
				{
					"name": name,
					"document_type": doc.document_type,
					"val": str(val)[:200],
					"ops": ops,
				},
			)
		except Exception as e:
			_log("H4", "probe.card_result", "fail", {"name": name, "err": str(e)[:400], "ops": ops})

	return {"ops": ops, "cards": card_names}


def probe_as_coordinator(user="nived@sevamrita.org"):
	"""Simulate ops access by temporarily adding NGO Coordinator role in-memory."""
	frappe.set_user(user)
	# Role add is durable — use flag override instead
	from volunteering.volunteering import volunteering_access

	orig = volunteering_access.user_has_volunteering_ops_access

	def _yes(_user=None):
		return True

	volunteering_access.user_has_volunteering_ops_access = _yes
	try:
		# also patch imports in permission modules
		import volunteering.volunteering.participation_permissions as pp
		import volunteering.volunteering.reciprocation_permissions as rp
		import volunteering.volunteering.volunteer_permissions as vp

		pp.user_has_volunteering_ops_access = _yes
		rp.user_has_volunteering_ops_access = _yes
		vp.user_has_volunteering_ops_access = _yes
		return probe(user)
	finally:
		volunteering_access.user_has_volunteering_ops_access = orig
		pp.user_has_volunteering_ops_access = orig
		rp.user_has_volunteering_ops_access = orig
		vp.user_has_volunteering_ops_access = orig
