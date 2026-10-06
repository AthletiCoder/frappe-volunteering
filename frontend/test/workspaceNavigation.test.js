import assert from "node:assert/strict";
import test from "node:test";
import { buildSidebarItems, homeFocus } from "../src/lib/workspaceNavigation.js";

const action = (id, group) => ({
	id,
	label: id,
	route: `/volunteering/${group}/${id}`,
	list_route: `/volunteering/${group}/${id}/history`,
	list_label: `${id} history`,
});

test("employee Home keeps a small personal focus while sidebar retains all work options", () => {
	const payload = {
		flags: { show_member_projects: true, can_create_projects: true },
		nav: { projects: true, advances: true },
		actions: {
			projects: [action("create_project", "projects"), action("approved_projects", "projects"), action("my_project_requests", "projects")],
			money: [action("claim", "money"), action("advance", "money"), action("invoice_generator", "money"), action("invoice_expense_claim", "money"), action("bank_account", "money"), action("future_money_action", "money")],
			time: [action("log_work", "time"), action("wfh", "time"), action("leave", "time"), action("fix_attendance", "time")],
			organisation: [action("office_addresses", "organisation")],
		},
	};
	const items = buildSidebarItems(payload);
	const menuLinks = items.flatMap((item) => item.children || []).map((child) => child.href);
	for (const group of Object.values(payload.actions)) for (const row of group) {
		assert.ok(menuLinks.includes(row.route), `${row.id} is missing from menu`);
		assert.ok(menuLinks.includes(row.list_route), `${row.id} history is missing from menu`);
	}
	assert.deepEqual(items.filter((item) => item.children).map((item) => item.label), ["Projects", "Expenses & invoices", "Advances", "Time & leave", "Organisation resources"]);
	const focus = homeFocus(payload);
	assert.deepEqual(focus.projectActions.map((row) => row.id), ["create_project", "my_project_requests"]);
	assert.deepEqual(focus.personalActions.map((row) => row.id), ["log_work", "leave"]);
	assert.ok(!focus.personalActions.some((row) => ["claim", "advance"].includes(row.id)));
});

test("combined management roles keep every permitted link but Home shows selected responsibilities", () => {
	const payload = {
		flags: { show_member_projects: false, can_create_projects: true },
		nav: { projects: true, budget_health: true, volunteering: true },
		actions: {
			projects: [action("create_project", "projects"), action("approved_projects", "projects"), action("my_project_requests", "projects"), action("review_project_proposals", "projects")],
			accounts: [action("advance_disbursement", "accounts"), action("advance_returns", "accounts"), action("donations", "accounts"), action("chart_of_accounts", "accounts"), action("opening_balances", "accounts"), action("project_account_mapping", "accounts")],
			hr_management: [action("manage_employees", "hr")],
			system_management: [action("manage_users", "system")],
			team: [action("my_team", "team")],
			money: [action("claim", "money"), action("advance", "money")],
		},
		people: [{ route: "/desk/hr-report", label: "HR report" }],
		admin: [{ route: "/desk/accounting-settings", label: "Accounting settings" }],
		programs: { workspace_route: "/desk/volunteering", report_route: "/desk/event-report" },
	};
	const menuLinks = buildSidebarItems(payload).flatMap((item) => item.children || []).map((child) => child.href);
	for (const group of Object.values(payload.actions)) for (const row of group) assert.ok(menuLinks.includes(row.route), `${row.id} is missing`);
	for (const route of ["/volunteering/budget-health", "/desk/hr-report", "/desk/accounting-settings", "/desk/volunteering", "/desk/event-report"]) assert.ok(menuLinks.includes(route));
	assert.ok(menuLinks.includes("/volunteering/expense-claim-workflow?view=classification"));
	assert.ok(menuLinks.includes("/volunteering/expense-claim-workflow?view=reimbursement"));
	const focus = homeFocus(payload);
	assert.deepEqual(focus.roleActions.map((row) => row.id), ["manage_users", "manage_employees", "review_project_proposals", "classify_claims", "settle_claims", "advance_disbursement", "donations", "opening_balances", "my_team"]);
	assert.deepEqual(focus.personalActions, []);
	assert.ok(!focus.roleActions.some((row) => row.id === "chart_of_accounts"));
});

test("accounts users get settlement but not manager-only classification", () => {
	const menuLinks = buildSidebarItems({ actions: { accounts: [action("advance_disbursement", "accounts")] } })
		.flatMap((item) => item.children || []).map((child) => child.href);
	assert.ok(menuLinks.includes("/volunteering/expense-claim-workflow?view=reimbursement"));
	assert.ok(!menuLinks.includes("/volunteering/expense-claim-workflow?view=classification"));
});

test("unassigned users see no role-specific links", () => {
	const items = buildSidebarItems({ actions: {}, nav: {}, waiting_count: 0 });
	assert.deepEqual(items.map((item) => item.label), ["Home", "My Work", "Profile"]);
	assert.deepEqual(homeFocus({ actions: {}, flags: {} }), { roleActions: [], projectActions: [], personalActions: [] });
});
