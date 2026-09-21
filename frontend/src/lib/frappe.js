export async function call(method, args = {}) {
	const res = await fetch(`/api/method/${method}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Accept: "application/json",
			"X-Requested-With": "XMLHttpRequest",
			"X-Frappe-CSRF-Token": window.csrf_token || "",
		},
		credentials: "include",
		body: JSON.stringify(args),
	});
	const responseText = await res.text();
	let data = {};
	try {
		data = responseText ? JSON.parse(responseText) : {};
	} catch (_) {
		if (!res.ok) {
			throw new Error(`Request failed (${res.status})`);
		}
		throw new Error("The server returned an invalid response.");
	}
	// Frappe also sends advisory msgprint warnings in _server_messages after
	// successful requests.  Only failed responses/exceptions are errors.
	if (!res.ok || data.exc || data.exception) {
		let msg = data.exception || data.exc || "Request failed";
		try {
			const server = JSON.parse(data._server_messages || "[]");
			if (server[0]) msg = JSON.parse(server[0]).message || msg;
		} catch (_) {}
		if (typeof msg === "string") {
			msg = msg.replace(/<[^>]+>/g, "");
		}
		throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
	}
	return data.message;
}
