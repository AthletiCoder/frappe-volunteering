const ROOT = "/api/method/";
export const APP_API = "volunteering.volunteering.collaboration_mobile.";
export const PWA_API = "volunteering.volunteering.tasks_pwa.";
export let csrf = "";
export function setCSRF(value) {
	csrf = value || "";
}
export async function request(method, args = {}, verb = "POST") {
	const response = await fetch(ROOT + method, {
		method: verb,
		credentials: "same-origin",
		cache: "no-store",
		redirect: "error",
		signal: AbortSignal.timeout(25000),
		headers: {
			Accept: "application/json",
			"Content-Type": "application/json",
			"X-Frappe-CSRF-Token": csrf,
			"X-Requested-With": "XMLHttpRequest",
		},
		...(verb === "POST" ? { body: JSON.stringify(args) } : {}),
	});
	let data;
	try {
		data = await response.json();
	} catch {
		throw Object.assign(
			new Error("The server returned an unexpected response. Please try again."),
			{ status: response.status },
		);
	}
	if (!response.ok || data.exc || data.exception) {
		let text = data.message || "Unable to complete this action.";
		try {
			text = JSON.parse(JSON.parse(data._server_messages)[0]).message || text;
		} catch {
			/* no public server message */
		}
		if (response.status === 401) text = "Sign in again to send your saved changes.";
		throw Object.assign(new Error(String(text).replace(/<[^>]*>/g, "")), {
			status: response.status,
		});
	}
	return data.message;
}
export const call = (method, args) => request(APP_API + method, args);
export async function session() {
	const result = await request(PWA_API + "get_session", {}, "GET");
	setCSRF(result.csrf_token);
	return result;
}
export async function filePayload(files) {
	if (
		files.length > 5 ||
		files.some(
			(file) =>
				!file.size ||
				file.size > 10485760 ||
				file.name.length > 180 ||
				!/\.(pdf|png|jpe?g|gif|webp|txt|csv|docx|xlsx)$/i.test(file.name),
		)
	)
		throw new Error(
			"Choose up to five PDF, image, text, Word or Excel files, each up to 10 MB.",
		);
	return Promise.all(
		files.map(
			(file) =>
				new Promise((resolve, reject) => {
					const reader = new FileReader();
					reader.onerror = () => reject(new Error(`Cannot read ${file.name}.`));
					reader.onload = () =>
						resolve({
							filename: file.name,
							content: String(reader.result).split(",")[1],
						});
					reader.readAsDataURL(file);
				}),
		),
	);
}
