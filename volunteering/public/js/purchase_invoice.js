frappe.ui.form.on("Purchase Invoice", {
	refresh(frm) {
		if (frm.doc.docstatus !== 1 || !(frm.doc.outstanding_amount > 0)) {
			return;
		}
		const accounts = frappe.user.has_role([
			"Accounts Manager",
			"Accounts User",
			"System Manager",
		]);
		if (!accounts) {
			return;
		}
		frm.add_custom_button(
			__("Mark Paid (outside system)"),
			() => {
				frappe.prompt(
					[
						{
							fieldname: "remarks",
							label: __("Remarks"),
							fieldtype: "Small Text",
							reqd: 1,
							default: __("Paid outside ERPNext"),
						},
						{
							fieldname: "posting_date",
							label: __("Payment Date"),
							fieldtype: "Date",
							default: frappe.datetime.get_today(),
							reqd: 1,
						},
					],
					(values) => {
						frappe.call({
							method:
								"volunteering.volunteering.reimbursement_controls.mark_purchase_invoice_paid_outside",
							args: {
								name: frm.doc.name,
								remarks: values.remarks,
								posting_date: values.posting_date,
							},
							freeze: true,
							callback() {
								frm.reload_doc();
							},
						});
					},
					__("Paid outside ERPNext"),
					__("Create Payment Entry")
				);
			},
			__("Actions")
		);
	},
});
