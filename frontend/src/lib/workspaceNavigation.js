// Keep navigation based on the server's permission-filtered Home payload.
// The sidebar is the complete action catalogue; Home only highlights likely starts.
const ACTION_ICONS = {
	create_project: "document-plus", approved_projects: "folder-check", my_project_requests: "document-history",
	review_project_proposals: "clipboard-check", claim: "receipt", invoice_generator: "invoice",
	invoice_expense_claim: "invoice-claim", advance: "coins", bank_account: "bank",
	log_work: "clock", wfh: "home", leave: "calendar-away", fix_attendance: "calendar-check",
	my_team: "people", donations: "coins", chart_of_accounts: "chart", opening_balances: "bank",
	project_account_mapping: "folder", manage_employees: "user-plus", manage_users: "user-shield",
	fiscal_years: "calendar-check",
};

function actionLinks(actions, ids) {
	const selected = ids ? actions.filter((action) => ids.includes(action.id)) : actions;
	return selected.flatMap((action) => [
		{ href: action.route, label: action.label, icon: ACTION_ICONS[action.id] || "arrow-right" },
		...(action.list_route ? [{ href: action.list_route, label: action.list_label, icon: "document-history", badge: action.pending || 0 }] : []),
	]);
}

function addGroup(items, id, label, icon, children) {
	const unique = [...new Map(children.filter((child) => child.href).map((child) => [child.href, child])).values()];
	if (unique.length) items.push({ id, label, icon, children: unique });
}

export function buildSidebarItems(payload) {
	const actions = payload?.actions || {};
	const nav = payload?.nav || {};
	const money = actions.money || [];
	const items = [
		{ to: "/home", label: "Home", icon: "home" },
		{ to: "/todos", label: "My Work", icon: "check", badge: payload?.waiting_count || 0 },
		{ to: "/profile", label: "Profile", icon: "user" },
	];

	const work = [];
	const projects = actionLinks(actions.projects || []);
	if (nav.projects && !projects.length) projects.push({ href: "/volunteering/projects?view=approved", label: "Approved projects", icon: "folder-check" });
	addGroup(work, "projects", "Projects", "folder", projects);
	// Any future money action remains discoverable even before Home chooses to highlight it.
	addGroup(work, "expenses", "Expenses & invoices", "receipt", actionLinks(money.filter((action) => action.id !== "advance")));
	const advances = actionLinks(money, ["advance"]);
	if (nav.advances && !advances.length) advances.push({ href: "/volunteering/advances", label: "Advance requests", icon: "wallet" });
	addGroup(work, "advances", "Advances", "wallet", advances);
	addGroup(work, "time", "Time & leave", "clock", actionLinks(actions.time || []));
	const team = actionLinks(actions.team || []);
	if (nav.team && !team.length) team.push({ href: "/volunteering/team", label: "My team", icon: "people" });
	addGroup(work, "team", "My team", "people", team);
	if (work.length) items.push({ section: "Your work" }, ...work);

	const management = [];
	const accounts = actionLinks(actions.accounts || []);
	if (actions.accounts?.length) {
		accounts.unshift({ href: "/volunteering/expense-claim-workflow?view=reimbursement", label: "Settle expense claims", icon: "money-out" });
		if (actions.accounts.some((action) => action.id === "chart_of_accounts"))
			accounts.unshift({ href: "/volunteering/expense-claim-workflow?view=classification", label: "Classify expense claims", icon: "receipt" });
	}
	if (nav.budget_health) accounts.push({ href: "/volunteering/budget-health", label: "Budget health", icon: "chart" });
	for (const link of payload?.admin || []) accounts.push({ href: link.route, label: link.label, icon: "chart" });
	addGroup(management, "accounts", "Accounts", "bank", accounts);
	addGroup(management, "hr", "HR management", "user-plus", [
		...actionLinks(actions.hr_management || []),
		...(payload?.people || []).map((link) => ({ href: link.route, label: link.label, icon: "people" })),
	]);
	addGroup(management, "system", "System management", "user-shield", actionLinks(actions.system_management || []));
	if (management.length) items.push({ section: "Management" }, ...management);

	const organisation = actionLinks(actions.organisation || []);
	if (payload?.programs) {
		organisation.push({ href: payload.programs.workspace_route, label: "Campaign dashboard", icon: "people" });
		organisation.push({ href: payload.programs.report_route, label: "Event report", icon: "chart" });
	} else if (nav.volunteering) {
		organisation.push({ href: "/desk/volunteering", label: "Volunteering", icon: "people" });
	}
	if (organisation.length) items.push({ section: "Organisation" });
	addGroup(items, "organisation", "Organisation resources", "map-pin", organisation);
	return items;
}

function pick(actions, ids) {
	return ids.flatMap((id) => actions.find((action) => action.id === id) || []);
}

export function homeFocus(payload) {
	const actions = payload?.actions || {};
	const accounts = actions.accounts || [];
	const accountsManager = accounts.some((action) => action.id === "chart_of_accounts");
	const roleActions = [
		...pick(actions.system_management || [], ["manage_users"]),
		...pick(actions.system_management || [], ["fiscal_years"]),
		...pick(actions.hr_management || [], ["manage_employees"]),
		...pick(actions.projects || [], ["review_project_proposals"]),
		...(accountsManager ? [{ id: "classify_claims", label: "Classify expense claims", hint: "Choose the ledger accounts before approval and settlement.", route: "/volunteering/expense-claim-workflow?view=classification" }] : []),
		...(accounts.length ? [{ id: "settle_claims", label: "Settle expense claims", hint: "Record payment of approved claims.", route: "/volunteering/expense-claim-workflow?view=reimbursement" }] : []),
		...pick(accounts, ["advance_disbursement", "donations", "opening_balances"]),
		...pick(actions.team || [], ["my_team"]),
	];
	const projectActions = pick(actions.projects || [], ["create_project", "my_project_requests"]);
	const personalActions = payload?.flags?.show_member_projects
		? pick(actions.time || [], ["log_work", "leave"])
		: [
			...pick(actions.money || [], ["claim", "advance", "invoice_generator"]),
			...pick(actions.time || [], ["log_work", "leave"]),
		];
	return {
		roleActions: [...new Map(roleActions.map((action) => [action.id, action])).values()],
		projectActions: payload?.flags?.can_create_projects ? projectActions : [],
		personalActions: roleActions.length ? [] : personalActions,
	};
}
