frappe.ui.form.on("Leave Application", {
	refresh(frm) {
		set_default_leave_type(frm);
	},

	leave_category(frm) {
		update_leave_intro(frm);
	},
});

function set_default_leave_type(frm) {
	if (frm.doc.leave_type) {
		update_leave_intro(frm);
		return;
	}

	frappe.db.get_single_value("Leave Policy Settings", "default_leave_type").then((leave_type) => {
		if (leave_type) {
			frm.set_value("leave_type", leave_type);
		}
		update_leave_intro(frm);
	});
}

function update_leave_intro(frm) {
	const hints = {
		Normal: __(
			"N days of leave require N days advance notice (e.g. 3-day leave needs 3 days notice)."
		),
		Emergency: __(
			"For unplanned absence up to 3 consecutive days. Retroactive applications must be filed within 48 hours of return. Counts against the same 30-day leave balance."
		),
	};

	const hint = hints[frm.doc.leave_category];
	if (hint) {
		frm.set_intro(hint);
	}
}
