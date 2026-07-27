frappe.query_reports["Employee Advances with Residual"] = {
	filters: [
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			width: "80",
		},
	],
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) {
			return value;
		}
		if (column.fieldname === "residual_pct" && data.above_threshold) {
			value = `<span style="color:var(--red-600);font-weight:600">${value}</span>`;
		} else if (column.fieldname === "residual" && data.above_threshold) {
			value = `<span style="color:var(--orange-600);font-weight:600">${value}</span>`;
		}
		return value;
	},
};
