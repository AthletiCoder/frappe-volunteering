frappe.pages["pending-my-approval"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("My Approval"),
		single_column: true,
	});

	page.main.html('<div class="accounting-dashboard-list"></div>');

	const columns = [
		{
			label: "Document",
			format: (row) =>
				volunteering.accounting_dashboard.link(
					row.route,
					`${row.reference_doctype} ${row.reference_name}`
				),
		},
		{
			label: "State",
			fieldname: "workflow_state",
		},
		{
			label: "Amount",
			format: (row) => volunteering.accounting_dashboard.format_currency(row.amount),
		},
		{
			label: "Project",
			fieldname: "project",
		},
		{
			label: "Pending",
			fieldname: "age_label",
		},
		{
			label: "Actions",
			format: (row) => (row.available_actions || []).join(", "),
		},
	];

	function refresh() {
		frappe.call({
			method: "volunteering.volunteering.accounting_dashboard.pending_approvals.get_pending_approvals",
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
