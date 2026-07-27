export async function call(method, args = {}) {
	const res = await fetch(`/api/method/${method}`, {
		method: "POST",
		headers: {
			"Content-Type": "application/json",
			Accept: "application/json",
			"X-Frappe-CSRF-Token": window.csrf_token || "",
		},
		credentials: "include",
		body: JSON.stringify(args),
	});
	const data = await res.json();
	if (data.exc || data._server_messages) {
		let msg = data.exception || data.exc || "Request failed";
		try {
			const server = JSON.parse(data._server_messages || "[]");
			if (server[0]) msg = JSON.parse(server[0]).message || msg;
		} catch (_) {}
		throw new Error(typeof msg === "string" ? msg : JSON.stringify(msg));
	}
	return data.message;
}
