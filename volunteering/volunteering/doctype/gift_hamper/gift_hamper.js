frappe.ui.form.on('Gift Hamper', {
    refresh(frm) {
        // Calculate total when the form loads
        frm.trigger('calculate_total');
    }
});

frappe.ui.form.on('Gift Hamper Item', {
    item_code: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.item_code) {
            // Fetch valuation rate from Item master
            frappe.db.get_value('Item', row.item_code, 'valuation_rate', (r) => {
                frappe.model.set_value(cdt, cdn, 'unit_cost', r.valuation_rate || 0);
                frm.trigger('calculate_total');
            });
        }
    },
    qty: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'amount', row.qty * row.unit_cost);
        frm.trigger('calculate_total');
    },
    unit_cost: function(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        frappe.model.set_value(cdt, cdn, 'amount', row.qty * row.unit_cost);
        frm.trigger('calculate_total');
    }
});

frappe.ui.form.on('Gift Hamper', {
    calculate_total: function(frm) {
        let total = 0;
        (frm.doc.items || []).forEach(row => {
            total += (row.qty * row.unit_cost);
        });
        frm.set_value('total_cost', total);
    }
});