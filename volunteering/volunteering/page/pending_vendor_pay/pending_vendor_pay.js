frappe.pages["pending-vendor-pay"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Vendor Payments"),
		single_column: true,
	});

	page.main.html('<div class="accounting-dashboard-list"></div>');

	const columns = [
		{
			label: "Purchase Invoice",
			format: (row) =>
				volunteering.accounting_dashboard.link(row.route, row.name),
		},
		{
			label: "Supplier",
			format: (row) => row.supplier_name || row.supplier,
		},
		{
			label: "Outstanding",
			format: (row) => volunteering.accounting_dashboard.format_currency(row.amount),
		},
		{
			label: "Project",
			fieldname: "project",
		},
		{
			label: "Due Date",
			fieldname: "due_date_label",
		},
	];

	function refresh() {
		frappe.call({
			method: "volunteering.volunteering.accounting_dashboard.pending_payments.get_pending_vendor_payments",
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
