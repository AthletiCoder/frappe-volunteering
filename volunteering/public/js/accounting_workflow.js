frappe.provide("volunteering.accounting_workflow");

const WORKFLOW_ACTIONS = ["Approve", "Reject"];
const IDLE_WORKFLOW_STATES = ["Draft", "Rejected", "Approved"];

volunteering.accounting_workflow.setup_form = function (doctype) {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			volunteering.accounting_workflow.render_actions(frm);
			volunteering.accounting_workflow.show_spend_hints(frm);
			volunteering.accounting_workflow.toggle_exception_fields(frm);
			if (doctype === "Employee Advance") {
				volunteering.accounting_workflow.lock_advance_employee(frm);
				volunteering.accounting_workflow.hide_advance_account_fields(frm);
			}
			if (doctype === "Expense Claim") {
				volunteering.accounting_workflow.show_advance_link_hints(frm);
			}
		},
		is_emergency(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		total_claimed_amount(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		grand_total(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		advance_amount(frm) {
			volunteering.accounting_workflow.toggle_exception_fields(frm);
		},
		employee(frm) {
			if (doctype === "Expense Claim") {
				volunteering.accounting_workflow.show_advance_link_hints(frm);
			}
		},
	});
};

volunteering.accounting_workflow.lock_advance_employee = function (frm) {
	const full_access = frappe.user.has_role([
		"Accounts Manager",
		"Accounts User",
		"HR Manager",
		"HR User",
		"System Manager",
		"NGO Board Member",
		"NGO Board Chairperson",
	]);
	if (full_access) {
		return;
	}
	frm.set_df_property("employee", "read_only", 1);
	if (frm.is_new() && !frm.doc.employee) {
		frappe.db.get_value("Employee", { user_id: frappe.session.user }, "name").then((r) => {
			if (r && r.message && r.message.name) {
				frm.set_value("employee", r.message.name);
			}
		});
	}
};

volunteering.accounting_workflow.hide_advance_account_fields = function (frm) {
	const accounts = frappe.user.has_role(["Accounts Manager", "Accounts User", "System Manager"]);
	if (frm.fields_dict.advance_account) {
		frm.set_df_property("advance_account", "hidden", accounts ? 0 : 1);
	}
	if (frm.fields_dict.project) {
		frm.set_df_property("project", "hidden", 1);
	}
};

volunteering.accounting_workflow.clear_advance_link_hints = function (frm) {
	volunteering.form_hints.clear(frm);
	frm._advance_hint_comment = null;
};

volunteering.accounting_workflow.show_advance_link_hints = function (frm) {
	volunteering.accounting_workflow.clear_advance_link_hints(frm);
	if (!frm.doc.employee || frm.doc.docstatus !== 0) {
		return;
	}

	// refresh + employee both fire on new forms; keep only the latest response
	const employee = frm.doc.employee;
	volunteering.form_hints.run_once(frm, "advance_link", (token) =>
		frappe
			.xcall("volunteering.volunteering.employee_advance_controls.get_linkable_advances_hint", {
				employee,
			})
			.then((msg) => {
				if (
					!volunteering.form_hints.is_current(frm, "advance_link", token) ||
					frm.doc.employee !== employee
				) {
					return;
				}
				volunteering.form_hints.clear(frm);
				if (!msg) {
					return;
				}
				volunteering.form_hints.set_headline(frm, msg, "blue");
			})
			.catch(() => {})
	);
};

volunteering.accounting_workflow.show_spend_hints = function (frm) {
	if (frm.doc.docstatus !== 0 || frm.doc.workflow_state !== "Draft") {
		return;
	}
	volunteering.form_hints.set_headline(
		frm,
		__(
			'Prefer vendor payments for larger spends. See <a href="/help/accounts/how-to-spend" target="_blank">How to spend</a>.'
		)
	);
};

volunteering.accounting_workflow.toggle_exception_fields = function (frm) {
	const pending = frm.doc.workflow_state === "Pending Approval";
	const is_approver = frm.doc.pending_approver === frappe.session.user;
	const has_reason = !!(frm.doc.budget_override_reason || "").trim();
	const show_budget = has_reason || (pending && is_approver);

	if (frm.fields_dict.budget_section) {
		frm.set_df_property("budget_section", "hidden", show_budget ? 0 : 1);
		frm.set_df_property("budget_section", "collapsed", show_budget ? 0 : 1);
	}
	if (frm.fields_dict.budget_override_reason) {
		frm.set_df_property("budget_override_reason", "hidden", show_budget ? 0 : 1);
		frm.toggle_reqd("budget_override_reason", false);
	}

	if (frm.doctype === "Expense Claim" && frm.fields_dict.vendor_override_reason) {
		const show_vendor =
			!!(frm.doc.vendor_override_reason || "").trim() || !!frm.doc.is_emergency;
		frm.set_df_property("vendor_override_reason", "hidden", show_vendor ? 0 : 1);
	}
};

volunteering.accounting_workflow.render_actions = function (frm) {
	if (frm.doc.docstatus !== 0 || !frm.doc.workflow_state) {
		return;
	}
	if (IDLE_WORKFLOW_STATES.includes(frm.doc.workflow_state)) {
		return;
	}

	frappe
		.xcall("volunteering.volunteering.approval_routing.get_approver_action_flags", {
			doctype: frm.doctype,
			name: frm.doc.name,
		})
		.then((flags) => {
			if (!flags || !flags.is_pending_approver) {
				return;
			}

			frappe.workflow.get_transitions(frm.doc).then((transitions) => {
				const actions = (transitions || []).filter((transition) =>
					WORKFLOW_ACTIONS.includes(transition.action)
				);
				const by_name = {};
				actions.forEach((t) => {
					by_name[t.action] = t;
				});

				if (flags.can_approve && by_name.Approve) {
					frm.page.set_primary_action(__("Approve"), () =>
						volunteering.accounting_workflow.apply_action(frm, "Approve")
					);
				}

				if (by_name.Reject && flags.can_reject) {
					frm.add_custom_button(
						__("Reject"),
						() => volunteering.accounting_workflow.apply_action(frm, "Reject"),
						__("Review")
					);
				}

				if (flags.can_escalate) {
					frm.add_custom_button(
						__("Escalate"),
						() => volunteering.accounting_workflow.escalate(frm),
						__("Review")
					);
				}
			});
		});
};

volunteering.accounting_workflow.escalate = function (frm) {
	frappe.prompt(
		{
			fieldname: "escalation_reason",
			label: __("Escalation Reason"),
			fieldtype: "Small Text",
			reqd: 1,
		},
		(values) => {
			frappe.dom.freeze();
			frappe
				.xcall("volunteering.volunteering.approval_routing.escalate_document", {
					doctype: frm.doctype,
					name: frm.doc.name,
					escalation_reason: values.escalation_reason,
				})
				.then(() => frm.reload_doc())
				.finally(() => frappe.dom.unfreeze());
		},
		__("Escalate for higher approval")
	);
};

volunteering.accounting_workflow.apply_action = function (frm, action) {
	const apply = () => {
		frappe.dom.freeze();
		frappe
			.xcall("frappe.model.workflow.apply_workflow", { doc: frm.doc, action })
			.then((doc) => {
				frappe.model.sync(doc);
				frm.refresh();
			})
			.catch(() => {
				// Uncollapse budget reason if Approve failed for missing reason
				if (action === "Approve" && frm.fields_dict.budget_section) {
					frm.set_df_property("budget_section", "hidden", 0);
					frm.set_df_property("budget_section", "collapsed", 0);
					frm.set_df_property("budget_override_reason", "hidden", 0);
				}
			})
			.finally(() => frappe.dom.unfreeze());
	};

	if (frm.is_dirty()) {
		frm.save().then(apply);
		return;
	}

	apply();
};

volunteering.accounting_workflow.setup_form("Expense Claim");
volunteering.accounting_workflow.setup_form("Purchase Order");
volunteering.accounting_workflow.setup_form("Employee Advance");
