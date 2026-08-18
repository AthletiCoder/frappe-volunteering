frappe.provide("volunteering.home_redirect");

volunteering.home_redirect.HOME_URL = "/volunteering/home";

volunteering.home_redirect.is_legacy_hub = function () {
	const path = (window.location.pathname || "").toLowerCase();
	if (/\/(app|desk)\/my-work\/?$/.test(path) || /\/(app|desk)\/my-expenses\/?$/.test(path)) {
		return true;
	}
	const route = (frappe.get_route && frappe.get_route()) || [];
	const joined = route.join("/").toLowerCase().replace(/\s+/g, "-");
	return joined.indexOf("my-work") !== -1 || joined.indexOf("my-expenses") !== -1;
};

volunteering.home_redirect.go = function () {
	if (volunteering.home_redirect.is_legacy_hub()) {
		window.location.replace(volunteering.home_redirect.HOME_URL);
	}
};

$(document).on("app_ready", function () {
	volunteering.home_redirect.go();
	if (frappe.router && frappe.router.on) {
		frappe.router.on("change", volunteering.home_redirect.go);
	}
});
