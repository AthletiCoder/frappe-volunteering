export const purchaseTaxFields = [
	{ key: 'cgst', label: 'CGST included (INR)' },
	{ key: 'sgst', label: 'SGST / UTGST included (INR)' },
	{ key: 'igst', label: 'IGST included (INR)' },
	{ key: 'other_tax', label: 'Other tax included (INR)' },
];

const cents = value => {
	const amount = Number(value ?? 0);
	return Number.isFinite(amount) && amount >= 0 && Math.abs(amount * 100 - Math.round(amount * 100)) < 0.000001
		? Math.round(amount * 100) : null;
};

// Integer paise keep the preview and validation consistent with stored amounts.
export function purchaseTaxSummary(items = []) {
	let gross = 0, tax = 0;
	const rows = [];
	for (const row of items) {
		const amount = cents(row.amount);
		const components = Object.fromEntries(purchaseTaxFields.map(({ key }) => [key, cents(row.tax_breakup?.[key])]));
		if (amount === null || Object.values(components).some(value => value === null)) {
			return { error: 'Enter non-negative tax amounts with no more than two decimal places.', items: [] };
		}
		const included = Object.values(components).reduce((sum, value) => sum + value, 0);
		if (included > amount) return { error: `Included taxes cannot exceed the bill amount for ${row.label || 'this item'}.`, items: [] };
		if (components.igst && (components.cgst || components.sgst)) return { error: 'Use either IGST or CGST/SGST for one item, not both.', items: [] };
		gross += amount; tax += included;
		rows.push({ receipt_item: row.receipt_item, base_amount: (amount - included) / 100, total_tax: included / 100, ...Object.fromEntries(Object.entries(components).map(([key, value]) => [key, value / 100])) });
	}
	return { error: '', items: rows, gross_total: gross / 100, tax_total: tax / 100, base_total: (gross - tax) / 100 };
}
