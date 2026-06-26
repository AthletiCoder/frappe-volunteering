frappe.pages["pending-reimburse"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Reimbursements"),
		single_column: true,
	});

	page.main.html('<div class="accounting-dashboard-list"></div>');

	const columns = [
		{
			label: "Expense Claim",
			format: (row) =>
				volunteering.accounting_dashboard.link(row.route, row.name),
		},
		{
			label: "Employee",
			format: (row) => row.employee_name || row.employee,
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
			label: "Posting Date",
			fieldname: "modified_label",
		},
	];

	function refresh() {
		frappe.call({
			method: "volunteering.volunteering.accounting_dashboard.pending_payments.get_pending_reimbursements",
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
