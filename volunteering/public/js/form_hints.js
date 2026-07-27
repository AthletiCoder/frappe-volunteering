/**
 * Form hint helpers.
 *
 * Frappe's frm.set_intro / dashboard.set_headline_alert APPEND to the message
 * area without clearing. Calling them on every refresh (or from overlapping
 * async handlers) stacks the same text twice. Always clear first.
 */
frappe.provide("volunteering.form_hints");

volunteering.form_hints.clear = function (frm) {
	if (!frm || !frm.dashboard) {
		return;
	}
	frm.dashboard.clear_headline();
};

/**
 * Replace the form intro with a single message (or clear if empty).
 */
volunteering.form_hints.set_intro = function (frm, html, color) {
	volunteering.form_hints.clear(frm);
	if (!html) {
		return;
	}
	frm.set_intro(html, color || "blue");
};

/**
 * Replace the dashboard headline with a single message (or clear if empty).
 */
volunteering.form_hints.set_headline = function (frm, html, color) {
	volunteering.form_hints.clear(frm);
	if (!html) {
		return;
	}
	frm.dashboard.set_headline(html, color);
};

/**
 * Run an async refresh-time hint once. Later overlapping calls are ignored
 * when their token is stale (same pattern as advance-link hints).
 *
 * Usage:
 *   volunteering.form_hints.run_once(frm, "wfh_intro", async () => { ... });
 */
volunteering.form_hints.run_once = function (frm, key, fn) {
	const token_key = `_hint_token_${key}`;
	const token = (frm[token_key] = (frm[token_key] || 0) + 1);
	return Promise.resolve()
		.then(() => fn(token))
		.then((result) => {
			if (token !== frm[token_key]) {
				return null;
			}
			return result;
		})
		.catch(() => null);
};

volunteering.form_hints.is_current = function (frm, key, token) {
	return token === frm[`_hint_token_${key}`];
};
