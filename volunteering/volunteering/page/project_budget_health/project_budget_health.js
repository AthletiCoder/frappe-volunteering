frappe.pages["project-budget-health"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Budget Health"),
		single_column: true,
	});

	page.main.html('<div class="accounting-dashboard-list"></div>');

	const columns = [
		{
			label: "Project",
			format: (row) => volunteering.accounting_dashboard.link(row.route, row.project),
		},
		{ label: "Department", fieldname: "department" },
		{
			label: "Allocated",
			format: (row) => volunteering.accounting_dashboard.format_currency(row.allocated),
		},
		{
			label: "Consumed",
			format: (row) => volunteering.accounting_dashboard.format_currency(row.consumed),
		},
		{
			label: "Remaining",
			format: (row) => volunteering.accounting_dashboard.format_currency(row.remaining),
		},
		{
			label: "Used %",
			format: (row) => `${Math.round(row.utilisation_pct || 0)}%`,
		},
	];

	function refresh() {
		frappe.call({
			method: "volunteering.volunteering.budget_service.get_budget_health",
			callback: (r) => {
				volunteering.accounting_dashboard.render_table(
					page.main.find(".accounting-dashboard-list"),
					r.message || [],
					columns
				);
			},
		});
	}

	page.set_primary_action(__("Refresh"), refresh, "refresh");
	frappe.require("/assets/volunteering/js/accounting_dashboard.js", refresh);
};
