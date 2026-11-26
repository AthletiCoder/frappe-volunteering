// Keep navigation based on the server's permission-filtered Home payload.
// The sidebar is the complete action catalogue; Home only highlights likely starts.
const ACTION_ICONS = {
	chat: "chat", collaboration_work: "calendar-check",
	create_project: "document-plus", approved_projects: "folder-check", my_project_requests: "document-history",
	review_project_proposals: "clipboard-check", claim: "receipt", invoice_generator: "invoice",
	invoice_expense_claim: "invoice-claim", advance: "coins", bank_account: "bank",
	log_work: "clock", wfh: "home", leave: "calendar-away", fix_attendance: "calendar-check",
	my_team: "people", donations: "coins", chart_of_accounts: "chart", opening_balances: "bank",
	project_account_mapping: "folder", manage_employees: "user-plus", manage_users: "user-shield",
	fiscal_years: "calendar-check",
	vendor_purchases: "invoice",
	my_purchase_requests: "invoice", purchase_approvals: "clipboard-check", approved_purchases: "wallet",
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

// Intent first: the places people go every day sit at the top; role
// workspaces follow; the full module catalogue stays one click away under
// "Browse everything" so every permitted action remains in the sidebar.
export function buildSidebarItems(payload) {
	const actions = payload?.actions || {};
	const nav = payload?.nav || {};
	const money = actions.money || [];
	const items = [
		{ to: "/home", label: "Home", icon: "home" },
		{ to: "/todos", label: "Waiting", icon: "check", badge: payload?.waiting_count || 0 },
	];
	if (buildRecordKinds(payload).length) items.push({ to: "/records", label: "Records", icon: "document-history" });

	const workspaces = [];
	const team = actionLinks(actions.team || []);
	if (nav.team && !team.length) team.push({ href: "/volunteering/team", label: "My team", icon: "people" });
	addGroup(workspaces, "team", "My team", "people", team);
	const accounts = actionLinks(actions.accounts || []);
	if (actions.accounts?.length) {
		accounts.unshift({ href: "/volunteering/expense-claim-workflow?view=reimbursement", label: "Settle expense claims", icon: "money-out" });
		if (actions.accounts.some((action) => action.id === "expense_approval_limits"))
			accounts.unshift({ href: "/volunteering/expense-claim-workflow?view=classification", label: "Classify expense claims", icon: "receipt" });
	}
	if (nav.budget_health) accounts.push({ href: "/volunteering/budget-health", label: "Budget health", icon: "chart" });
	for (const link of payload?.admin || []) accounts.push({ href: link.route, label: link.label, icon: "chart" });
	addGroup(workspaces, "accounts", "Accounts", "bank", accounts);
	addGroup(workspaces, "hr", "HR management", "user-plus", [
		...actionLinks(actions.hr_management || []),
		...(payload?.people || []).map((link) => ({ href: link.route, label: link.label, icon: "people" })),
	]);
	addGroup(workspaces, "system", "System management", "user-shield", actionLinks(actions.system_management || []));
	if (workspaces.length) items.push({ section: "Workspaces" }, ...workspaces);

	const browse = [];
	const projects = actionLinks(actions.projects || []);
	if (nav.projects && !projects.length) projects.push({ href: "/volunteering/projects?view=approved", label: "Approved projects", icon: "folder-check" });
	addGroup(browse, "projects", "Projects", "folder", projects);
	// Any future money action remains discoverable even before Home chooses to highlight it.
	addGroup(browse, "expenses", "Expenses & invoices", "receipt", actionLinks(money.filter((action) => action.id !== "advance")));
	const advances = actionLinks(money, ["advance"]);
	if (nav.advances && !advances.length) advances.push({ href: "/volunteering/advances", label: "Advance requests", icon: "wallet" });
	addGroup(browse, "advances", "Advances", "wallet", advances);
	addGroup(browse, "purchasing", "Purchasing", "invoice", actionLinks(actions.purchasing || []));
	addGroup(browse, "time", "Time & leave", "clock", actionLinks(actions.time || []));
	addGroup(browse, "collaboration", "Collaboration", "chat", actionLinks(actions.collaboration || []));
	const organisation = actionLinks(actions.organisation || []);
	if (payload?.programs) {
		organisation.push({ href: payload.programs.workspace_route, label: "Campaign dashboard", icon: "people" });
		organisation.push({ href: payload.programs.report_route, label: "Event report", icon: "chart" });
	} else if (nav.volunteering) {
		organisation.push({ href: "/desk/volunteering", label: "Volunteering", icon: "people" });
	}
	addGroup(browse, "organisation", "Organisation resources", "map-pin", organisation);
	if (browse.length) items.push({ section: "Browse everything" }, ...browse);

	if (items.some((item) => item.section)) items.push({ section: "You" });
	items.push({ to: "/profile", label: "Profile", icon: "user" });
	return items;
}

// "+ New": every request a person can start, grouped by what it is for.
const NEW_GROUPS = [
	["Money", [["claim", "Submit an expense", "receipt"], ["claim_multiple", "Submit several invoices", "invoice-claim"], ["invoice_expense_claim", "Invoice and expense together", "invoice-claim"], ["invoice_generator", "Prepare an invoice", "invoice"], ["advance", "Request an advance", "coins"]]],
	["Time", [["log_work", "Log work", "clock"], ["leave", "Apply for leave", "calendar-away"], ["wfh", "Work from home", "home"], ["fix_attendance", "Fix attendance", "calendar-check"]]],
	["Projects and purchasing", [["create_project", "Propose a project", "document-plus"], ["my_purchase_requests", "Raise a purchase request", "vendor"]]],
];

export function buildNewActions(payload) {
	const all = Object.values(payload?.actions || {}).flat();
	const byId = new Map(all.map((action) => [action.id, action]));
	const claim = byId.get("claim");
	if (claim) byId.set("claim_multiple", { id: "claim_multiple", route: "/volunteering/expense-claim/multiple", hint: "For bills with different dates." });
	return NEW_GROUPS.map(([title, entries]) => ({
		title,
		items: entries.flatMap(([id, label, icon]) => {
			const action = byId.get(id);
			return action?.route ? [{ id, label, icon, href: action.route, hint: action.hint || "" }] : [];
		}),
	})).filter((group) => group.items.length);
}

// "Records": everything the person has raised, one list per kind.
const RECORD_KINDS = [
	["claim", "Expense claims", "receipt", "Receipts, approvals and payments"],
	["advance", "Advances", "coins", "Money received before spending"],
	["my_purchase_requests", "Purchase requests", "vendor", "Orders you raised"],
	["leave", "Time and leave", "calendar-away", "Leave, WFH and attendance fixes"],
	["log_work", "Work logs", "clock", "Daily logs and reviews"],
	["my_project_requests", "Project proposals", "document-history", "Proposals you prepared"],
	["approved_projects", "Projects", "folder-check", "Projects you belong to"],
	["bank_account", "Reimbursement bank account", "bank", "Where your reimbursements go"],
];

export function buildRecordKinds(payload) {
	const personal = [...(payload?.actions?.money || []), ...(payload?.actions?.time || []), ...(payload?.actions?.projects || []), ...(payload?.actions?.purchasing || [])];
	const byId = new Map(personal.map((action) => [action.id, action]));
	const seen = new Set();
	return RECORD_KINDS.flatMap(([id, label, icon, hint]) => {
		const action = byId.get(id);
		const href = action?.list_route || action?.route;
		if (!href || seen.has(href)) return [];
		seen.add(href);
		return [{ id, label, icon, hint, href, open: Number(action.pending || 0) }];
	});
}

function pick(actions, ids) {
	return ids.flatMap((id) => actions.find((action) => action.id === id) || []);
}

export function homeFocus(payload) {
	const actions = payload?.actions || {};
	const accounts = actions.accounts || [];
	const accountsManager = accounts.some((action) => action.id === "expense_approval_limits");
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
