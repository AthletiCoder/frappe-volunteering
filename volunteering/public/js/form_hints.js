/**
 * Form hint helpers + Desk blank-tab recovery.
 *
 * Frappe's frm.set_intro / dashboard.set_headline_alert APPEND without clearing.
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

volunteering.form_hints.TAB_FIX_DOCTYPES = {
	"Expense Claim": true,
	"Employee Advance": true,
	"Purchase Order": true,
};

volunteering.form_hints.ensure_form_body_visible = function (frm) {
	frm = frm || cur_frm;
	const layout = frm && frm.layout;
	if (!layout || !layout.tabs || !layout.tabs.length) {
		return false;
	}
	if (!volunteering.form_hints.TAB_FIX_DOCTYPES[frm.doctype]) {
		return false;
	}

	const first =
		layout.tabs.find(
			(tab) =>
				tab.wrapper &&
				tab.wrapper.find(".form-section:not(.empty-section), .form-dashboard-section").length
		) || layout.tabs[0];
	if (!first || !first.wrapper || !first.wrapper.length) {
		return false;
	}

	const height = first.wrapper[0].offsetHeight || 0;
	const already =
		first.wrapper.hasClass("active") && !first.wrapper.hasClass("hide") && height > 40;
	if (already) {
		return true;
	}

	layout.tabs.forEach((tab) => {
		if (!tab.wrapper || !tab.wrapper.length) {
			return;
		}
		if (tab === first) {
			tab.hidden = false;
			tab.wrapper.removeClass("hide").addClass("show active");
			if (tab.tab_link && tab.tab_link.length) {
				tab.tab_link.removeClass("hide").addClass("show");
				tab.tab_link.find(".nav-link").addClass("active");
			}
		} else {
			tab.wrapper.removeClass("show active").addClass("hide");
			if (tab.tab_link && tab.tab_link.length) {
				tab.tab_link.find(".nav-link").removeClass("active");
			}
		}
	});

	if (first.set_active) {
		first.set_active();
	}
	return (first.wrapper[0].offsetHeight || 0) > 40;
};

volunteering.form_hints.patch_frm_layout = function (frm) {
	frm = frm || cur_frm;
	if (!frm || !frm.layout || !frm.layout.refresh_tabs || frm.layout._vol_tabs_patched) {
		return;
	}
	const layout = frm.layout;
	const original = layout.refresh_tabs.bind(layout);
	layout.refresh_tabs = function (...args) {
		const result = original(...args);
		volunteering.form_hints.ensure_form_body_visible(frm);
		return result;
	};
	layout._vol_tabs_patched = true;
};

volunteering.form_hints.fix_blank_tabs = function () {
	const frm = cur_frm;
	if (!frm || !volunteering.form_hints.TAB_FIX_DOCTYPES[frm.doctype]) {
		return;
	}
	volunteering.form_hints.patch_frm_layout(frm);
	volunteering.form_hints.ensure_form_body_visible(frm);
};

volunteering.form_hints.start_blank_tab_guard = function () {
	if (volunteering.form_hints._guard_started) {
		return;
	}
	volunteering.form_hints._guard_started = true;

	$(document).on("form-refresh form-load", function (_event, frm) {
		volunteering.form_hints.patch_frm_layout(frm);
		volunteering.form_hints.ensure_form_body_visible(frm);
		setTimeout(volunteering.form_hints.fix_blank_tabs, 0);
		setTimeout(volunteering.form_hints.fix_blank_tabs, 200);
		setTimeout(volunteering.form_hints.fix_blank_tabs, 600);
		setTimeout(volunteering.form_hints.fix_blank_tabs, 1200);
	});

	// Route changes (Desk soft nav) often skip a usable form-refresh timing.
	if (frappe.router && frappe.router.on) {
		frappe.router.on("change", function () {
			setTimeout(volunteering.form_hints.fix_blank_tabs, 0);
			setTimeout(volunteering.form_hints.fix_blank_tabs, 300);
			setTimeout(volunteering.form_hints.fix_blank_tabs, 800);
		});
	}

	// Last resort: whenever a tab pane is marked hide, reopen content.
	const observer = new MutationObserver(function () {
		const frm = cur_frm;
		if (!frm || !volunteering.form_hints.TAB_FIX_DOCTYPES[frm.doctype]) {
			return;
		}
		const panes = document.querySelectorAll(".form-layout .tab-pane.hide");
		if (!panes.length) {
			return;
		}
		const anyVisible = document.querySelector(".form-layout .tab-pane.show.active:not(.hide)");
		if (anyVisible && anyVisible.offsetHeight > 40) {
			return;
		}
		volunteering.form_hints.fix_blank_tabs();
	});
	observer.observe(document.body, {
		subtree: true,
		attributes: true,
		attributeFilter: ["class"],
	});
	volunteering.form_hints._tab_observer = observer;
};

volunteering.form_hints.start_blank_tab_guard();
$(document).on("app_ready", volunteering.form_hints.start_blank_tab_guard);
