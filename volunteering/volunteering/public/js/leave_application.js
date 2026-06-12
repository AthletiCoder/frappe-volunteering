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
		Planned: __("Apply at least 14 days in advance. Shorter notice needs a detailed reason."),
		Emergency: __("For unplanned absence up to 2 consecutive days."),
		Sick: __("For illness. Apply for today or a future date; manager approval required."),
	};

	const hint = hints[frm.doc.leave_category];
	if (hint) {
		frm.set_intro(hint);
	}
}
