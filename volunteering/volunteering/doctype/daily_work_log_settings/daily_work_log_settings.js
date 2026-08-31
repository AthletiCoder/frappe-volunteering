frappe.ui.form.on("Daily Work Log Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Preview Summary"), () => preview_digest(frm), __("Work Log Summary"));
		frm.add_custom_button(__("Send Summary Now"), () => send_digest_now(frm), __("Work Log Summary"));
		frm.add_custom_button(
			__("Send Missing-Log Reminders Now"),
			() => send_reminders_now(frm),
			__("Missing Log Reminder")
		);
	},
});

function preview_digest(frm) {
	frappe.call({
		method: "volunteering.volunteering.api.attendance_digest.preview_work_log_digest",
		freeze: true,
		freeze_message: __("Building preview…"),
		callback(r) {
			const data = r.message || {};
			const recipients = (data.recipients || []).join(", ") || __("(no recipients configured)");
			const dialog = new frappe.ui.Dialog({
				title: __("{0} Summary Preview", [data.label || ""]),
				size: "large",
				fields: [
					{
						fieldtype: "HTML",
						fieldname: "preview",
					},
				],
			});
			dialog.fields_dict.preview.$wrapper.html(
				`<p style="font-size:12px;color:#64748b;margin-bottom:12px;">
					<b>${__("Recipients")}:</b> ${frappe.utils.escape_html(recipients)}
				</p>` + (data.html || "")
			);
			dialog.show();
		},
	});
}

function send_digest_now(frm) {
	frappe.confirm(
		__("Send the work log summary email now to all configured recipients?"),
		() => {
			frappe.call({
				method: "volunteering.volunteering.api.attendance_digest.send_work_log_digest_now",
				freeze: true,
				freeze_message: __("Sending…"),
				callback(r) {
					const data = r.message || {};
					if (data.skipped) {
						frappe.msgprint({
							title: __("Not Sent"),
							message: __("Skipped: {0}", [data.reason || "unknown"]),
							indicator: "orange",
						});
						return;
					}
					frappe.show_alert({
						message: __("Summary sent to {0} recipient(s).", [(data.recipients || []).length]),
						indicator: "green",
					});
				},
			});
		}
	);
}

function send_reminders_now(frm) {
	frappe.confirm(
		__(
			"Email paid employees who are missing a submitted work log for yesterday? (Holidays, leave, and people who already logged are skipped.)"
		),
		() => {
			frappe.call({
				method: "volunteering.volunteering.api.work_log_reminder.send_missing_log_reminders_now",
				freeze: true,
				freeze_message: __("Sending reminders…"),
				callback(r) {
					const data = r.message || {};
					if (data.skipped) {
						frappe.msgprint({
							title: __("Not Sent"),
							message: __("Skipped: {0}", [data.reason || "unknown"]),
							indicator: "orange",
						});
						return;
					}
					frappe.show_alert({
						message: __("Reminders sent: {0}. Skipped: {1}.", [
							data.sent || 0,
							data.skipped || 0,
						]),
						indicator: "green",
					});
				},
			});
		}
	);
}
