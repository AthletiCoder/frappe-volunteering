frappe.provide("volunteering.accounting_dashboard");

volunteering.accounting_dashboard.render_table = function (parent, rows, columns) {
	const $parent = $(parent);
	$parent.empty();

	if (!rows || !rows.length) {
		$parent.html(
			`<div class="text-muted text-center padding">${__("No pending items")}</div>`
		);
		return;
	}

	const $table = $(`
		<div class="table-responsive">
			<table class="table table-bordered table-hover">
				<thead></thead>
				<tbody></tbody>
			</table>
		</div>
	`);

	const $thead = $table.find("thead");
	const $tbody = $table.find("tbody");

	const header = columns.map((col) => `<th>${__(col.label)}</th>`).join("");
	$thead.html(`<tr>${header}</tr>`);

	rows.forEach((row) => {
		const cells = columns
			.map((col) => {
				const value = col.format ? col.format(row) : row[col.fieldname] || "";
				return `<td>${value}</td>`;
			})
			.join("");
		$tbody.append(`<tr>${cells}</tr>`);
	});

	$parent.append($table);
};

volunteering.accounting_dashboard.link = function (route, label) {
	if (!route) return label || "";
	const href = route.startsWith("/") ? route : `/app/${route}`;
	return `<a href="${href}">${frappe.utils.escape_html(label || route)}</a>`;
};

volunteering.accounting_dashboard.format_currency = function (amount) {
	return frappe.format(amount, { fieldtype: "Currency" });
};
