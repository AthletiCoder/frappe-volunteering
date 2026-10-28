"""Give existing localhost demo fixtures realistic, clearly marked tutorial labels.

This is opt-in, local-only and cosmetic. It does not create or delete vouchers,
change passwords, or alter workflow states or ledger entries.
"""

import frappe


SITE = "sevamrita.local"

PEOPLE = {
	"demo.tonight.proposer@sevamrita.local": "Arjun Deshpande",
	"demo.tonight.projectmanager@sevamrita.local": "Mohan Iyer",
	"demo.tonight.employee@sevamrita.local": "Rahul Patil",
	"demo.tonight.receipts@sevamrita.local": "Priya Nair",
	"demo.tonight.manager@sevamrita.local": "Sanjay Kulkarni",
	"demo.tonight.director@sevamrita.local": "Kavita Rao",
	"demo.tonight.board@sevamrita.local": "Arun Menon",
	"demo.tonight.accounts@sevamrita.local": "Nandita Shah",
	"demo.tonight.advance.manager@sevamrita.local": "Vivek Sharma",
	"demo.tonight.advance.director@sevamrita.local": "Ritika Reddy",
	"demo.tonight.advance.board@sevamrita.local": "Neha Bhat",
	"demo.tonight.advance.approved@sevamrita.local": "Farhan Ali",
	"demo.tonight.advance.paid@sevamrita.local": "Deepa Joshi",
}

# The original demo stage keys are used to find only the known tutorial fixtures.
PROJECTS = {
	"Draft project proposal": (
		"Training Demo — Pune Community Library Initiative",
		"Set up a neighbourhood reading room with books and weekly volunteer sessions.",
		"A stocked reading room and a regular schedule for local children.",
	),
	"Pending project proposal": (
		"Training Demo — Mumbai School Nutrition Programme",
		"Provide nutritious snacks to children attending after-school classes.",
		"A reliable snack distribution plan and attendance records.",
	),
	"Returned project proposal": (
		"Training Demo — Sangareddy Rural Health Camp",
		"Organise a community health screening camp with local clinicians.",
		"Screening records and follow-up referrals for participating residents.",
	),
	"Rejected project proposal": (
		"Training Demo — Hyderabad Sports Outreach",
		"Explore weekend sports sessions for children in underserved areas.",
		"A reviewed proposal with documented feedback.",
	),
	"Approved planned project": (
		"Training Demo — Talegaon Tree Planting Drive",
		"Plant and maintain native trees with community volunteers.",
		"A planting plan and follow-up care schedule.",
	),
	"Approved active project": (
		"Training Demo — Balewadi Digital Learning Centre",
		"Provide tablets and after-school digital learning support to local students.",
		"Regular learning sessions, attendance and learning materials.",
	),
	"Approved on hold project": (
		"Training Demo — Powai Skills Workshop",
		"Offer practical livelihood workshops with local trainers.",
		"A documented workshop plan ready to restart.",
	),
	"Approved completed project": (
		"Training Demo — Medak Winter Clothing Drive",
		"Collect and distribute winter clothing to families in need.",
		"Completed distribution records and project closure.",
	),
}


def execute():
	if frappe.local.site != SITE:
		frappe.throw(f"Tutorial data may only be changed on {SITE}.")

	# Check all targets first: a partial demo set should be repaired explicitly,
	# not silently renamed or supplemented with extra accounts or projects.
	missing_users = [email for email in PEOPLE if not frappe.db.exists("User", email)]
	if missing_users:
		frappe.throw("Seed the existing local demo first; missing users: " + ", ".join(missing_users))

	proposal_names = {}
	for stage, (title, _purpose, _outcome) in PROJECTS.items():
		proposal_name = (
			frappe.db.get_value("Project Proposal", {"title": title}, "name")
			or frappe.db.get_value("Project Proposal", {"title": f"Tonight Demo {stage}"}, "name")
		)
		if not proposal_name:
			frappe.throw(f"Existing local demo proposal is missing: {stage}")
		proposal_names[stage] = proposal_name

	for email, full_name in PEOPLE.items():
		first_name, last_name = full_name.split(" ", 1)
		frappe.db.set_value(
			"User", email,
			{"first_name": first_name, "last_name": last_name, "full_name": full_name},
		)
		employee = frappe.db.get_value("Employee", {"user_id": email}, "name")
		if employee:
			frappe.db.set_value(
				"Employee", employee,
				{"first_name": first_name, "last_name": last_name, "employee_name": full_name},
			)

	for stage, (title, purpose, outcome) in PROJECTS.items():
		proposal = proposal_names[stage]
		proposal_data = frappe.parse_json(
			frappe.db.get_value("Project Proposal", proposal, "proposal_data") or "{}"
		)
		if isinstance(proposal_data, dict):
			proposal_data.update({
				"project_name": title,
				"project_purpose": purpose,
				"project_outcomes": outcome,
			})
		frappe.db.set_value(
			"Project Proposal", proposal,
			{"title": title, "proposal_data": frappe.as_json(proposal_data)},
		)
		project = frappe.db.get_value("Project Proposal", proposal, "project")
		if project:
			frappe.db.set_value(
				"Project", project,
				{"project_name": title, "project_purpose": purpose, "project_outcomes": outcome},
			)
	frappe.db.commit()
	return {"people": len(PEOPLE), "projects": len(PROJECTS), "site": SITE}
