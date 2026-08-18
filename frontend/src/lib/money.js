export function formatMoney(v) {
	return new Intl.NumberFormat(undefined, {
		style: "currency",
		currency: "INR",
		maximumFractionDigits: 0,
	}).format(v || 0);
}
