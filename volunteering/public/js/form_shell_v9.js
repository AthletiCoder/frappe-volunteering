/**
 * Form hint helpers + minimal Desk tab hash fix.
 *
 * Frappe Form.set_active_tab writes
 *   fieldname.replace("__details", "")
 * into the URL hash. For Expense Claim that turns
 *   accounting_details_tab → accounting_tab
 * so the next layout.refresh_tabs cannot resolve the tab and falls back to tab 1
 * (blank Accounting / jump to Expenses).
 *
 * Do NOT monkey-patch refresh_tabs or force-activate tabs — that remounted new
 * docs (docname changed in the URL).
 */
frappe.provide("volunteering.form_hints");

volunteering.form_hints.clear = function (frm) {
	if (!frm || !frm.dashboard) {
		return;
	}
	frm.dashboard.clear_headline();
};

volunteering.form_hints.set_intro = function (frm, html, color) {
	volunteering.form_hints.clear(frm);
	if (!html) {
		return;
	}
	frm.set_intro(html, color || "blue");
};

volunteering.form_hints.set_headline = function (frm, html, color) {
	volunteering.form_hints.clear(frm);
	if (!html) {
		return;
	}
	frm.dashboard.set_headline(html, color);
};

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

volunteering.form_hints._resolve_tab_from_hash = function (layout, hash) {
	if (!layout || !hash || !layout.tabs) {
		return null;
	}
	return (
		layout.tabs.find((tab) => tab.df && tab.df.fieldname === hash) ||
		layout.tabs.find((tab) => tab.df && (tab.df.fieldname || "").replace("__details", "") === hash) ||
		null
	);
};

volunteering.form_hints.patch_tab_hash_bug = function () {
	if (volunteering.form_hints._tab_hash_patched) {
		return;
	}
	if (!frappe.ui || !frappe.ui.form || !frappe.ui.form.Form || !frappe.ui.form.Layout) {
		return;
	}

	const Form = frappe.ui.form.Form;
	if (Form.prototype.set_active_tab && !Form.prototype._vol_set_active_tab_patched) {
		const original = Form.prototype.set_active_tab;
		Form.prototype.set_active_tab = function (tab) {
			const previous_tab_name = this.active_tab_map?.[this.docname]?.df?.fieldname || "";
			const next_tab_name = tab?.df?.fieldname || "";
			const has_changed = previous_tab_name !== next_tab_name;

			// Run original (updates map / on_tab_change / broken hash).
			original.apply(this, arguments);

			// Restore a resolvable hash — never the mangled "__details" strip.
			if (has_changed && next_tab_name && window.history && window.history.replaceState) {
				const url = new URL(window.location.href);
				if (url.hash.replace("#", "") !== next_tab_name) {
					url.hash = next_tab_name;
					history.replaceState(null, null, url);
				}
			}
		};
		Form.prototype._vol_set_active_tab_patched = true;
	}

	const Layout = frappe.ui.form.Layout;
	if (Layout.prototype.set_tab_as_active && !Layout.prototype._vol_set_tab_as_active_patched) {
		const original = Layout.prototype.set_tab_as_active;
		Layout.prototype.set_tab_as_active = function (...args) {
			const hash = (window.location.hash || "").replace("#", "");
			const tab = volunteering.form_hints._resolve_tab_from_hash(this, hash);
			if (tab && hash && tab.df.fieldname !== hash && window.history && window.history.replaceState) {
				const url = new URL(window.location.href);
				url.hash = tab.df.fieldname;
				history.replaceState(null, null, url);
			}
			return original.apply(this, args);
		};
		Layout.prototype._vol_set_tab_as_active_patched = true;
	}

	volunteering.form_hints._tab_hash_patched = true;
};

// Back-compat no-ops for older callers.
volunteering.form_hints.TAB_FIX_DOCTYPES = {};
volunteering.form_hints.ensure_form_body_visible = function () {
	return false;
};
volunteering.form_hints.patch_frm_layout = function () {};
volunteering.form_hints.fix_blank_tabs = function () {};
volunteering.form_hints.start_blank_tab_guard = function () {
	volunteering.form_hints.patch_tab_hash_bug();
};

volunteering.form_hints.patch_tab_hash_bug();
$(document).on("app_ready", volunteering.form_hints.patch_tab_hash_bug);
