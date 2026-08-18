frappe.ui.form.on("Project", {
	refresh(frm) {
		if (!frm.doc.name || frm.is_new()) {
			return;
		}
		volunteering.form_hints.run_once(frm, "project_budget", () =>
			frappe
				.xcall("volunteering.volunteering.budget_service.get_budget_snapshot", {
					project: frm.doc.name,
				})
				.then((snap) => {
					if (!snap || !snap.allocated) {
						volunteering.form_hints.set_headline(
							frm,
							__(
								"Set Department Budgets below (approved amount per department). Spend is checked on Expense Claims and Purchase Orders, not advances."
							)
						);
						return;
					}
					const allocated = format_currency(snap.allocated);
					const spent = format_currency(snap.consumed);
					const available = format_currency(snap.remaining);
					volunteering.form_hints.set_headline(
						frm,
						__("Approved {0} · Spent {1} · Available {2}", [allocated, spent, available])
					);
				})
		);
	},
});
