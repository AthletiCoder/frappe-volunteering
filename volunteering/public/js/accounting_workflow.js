frappe.provide("volunteering.accounting_workflow");

const WORKFLOW_ACTIONS = ["Approve", "Reject", "Escalate"];
const IDLE_WORKFLOW_STATES = ["Draft", "Rejected", "Approved"];

volunteering.accounting_workflow.setup_form = function (doctype) {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			volunteering.accounting_workflow.render_actions(frm);
		},
	});
};

volunteering.accounting_workflow.render_actions = function (frm) {
	if (frm.doc.docstatus !== 0 || !frm.doc.workflow_state) {
		return;
	}
	if (IDLE_WORKFLOW_STATES.includes(frm.doc.workflow_state)) {
		return;
	}

	frappe.workflow.get_transitions(frm.doc).then((transitions) => {
		const actions = (transitions || []).filter((transition) =>
			WORKFLOW_ACTIONS.includes(transition.action)
		);
		if (!actions.length) {
			return;
		}

		actions.forEach((transition) => {
			const is_primary = transition.action === "Approve";
			frm.add_custom_button(
				__(transition.action),
				() => volunteering.accounting_workflow.apply_action(frm, transition.action),
				is_primary ? __("Review") : __("Review")
			);
		});
	});
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
			.finally(() => frappe.dom.unfreeze());
	};

	if (action === "Escalate") {
		frappe.prompt(
			{
				fieldname: "escalation_reason",
				label: __("Escalation Reason"),
				fieldtype: "Small Text",
				reqd: 1,
			},
			(values) => {
				frm.set_value("escalation_reason", values.escalation_reason);
				frm.save().then(apply);
			},
			__("Escalate for higher approval")
		);
		return;
	}

	if (frm.is_dirty()) {
		frm.save().then(apply);
		return;
	}

	apply();
};

volunteering.accounting_workflow.setup_form("Expense Claim");
volunteering.accounting_workflow.setup_form("Purchase Order");
