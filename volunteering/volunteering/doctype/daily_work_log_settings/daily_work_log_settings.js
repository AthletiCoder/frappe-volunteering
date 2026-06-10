frappe.ui.form.on("Daily Work Log Settings", {
	refresh(frm) {
		if (
			!frappe.user.has_role("HR Manager") &&
			!frappe.user.has_role("System Manager")
		) {
			return;
		}

		frm.add_custom_button(__("Process Attendance"), () => {
			const yesterday = frappe.datetime.add_days(frappe.datetime.get_today(), -1);

			frappe.prompt(
				[
					{
						label: __("Attendance Date"),
						fieldname: "attendance_date",
						fieldtype: "Date",
						reqd: 1,
						default: yesterday,
					},
				],
				(values) => {
					frappe.call({
						method:
							"volunteering.volunteering.doctype.daily_work_log_settings.daily_work_log_settings.trigger_attendance_job",
						args: {
							attendance_date: values.attendance_date,
						},
						freeze: true,
						freeze_message: __("Processing attendance..."),
						callback(r) {
							const summary = r.message;
							if (!summary || summary.skipped) {
								return;
							}

							frappe.msgprint({
								title: __("Attendance Processed"),
								message: __(
									"Date: {0}<br>Employees processed: {1}<br>Created: {2}<br>Updated: {3}<br>Unchanged: {4}<br>Skipped: {5}<br>Errors: {6}",
									[
										summary.attendance_date,
										summary.processed,
										summary.created,
										summary.updated,
										summary.unchanged,
										summary.skipped,
										summary.errors,
									]
								),
								indicator: summary.errors ? "orange" : "green",
							});
						},
					});
				},
				__("Process Attendance"),
				__("Run")
			);
		});
	},
});
