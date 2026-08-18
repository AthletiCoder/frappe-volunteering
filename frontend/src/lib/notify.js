const STORAGE_KEY = "volunteering.todo.fingerprint";

export function todoFingerprint(payload) {
	const todos = payload?.todos || [];
	return todos
		.map((row) => row.id)
		.sort()
		.join("|");
}

export async function requestNotifyPermission() {
	if (typeof Notification === "undefined") {
		return "unsupported";
	}
	if (Notification.permission === "granted") {
		return "granted";
	}
	return Notification.requestPermission();
}

export function notifyPermission() {
	if (typeof Notification === "undefined") {
		return "unsupported";
	}
	return Notification.permission;
}

export function maybeNotifyNewTodos(payload) {
	const next = todoFingerprint(payload);
	const prev = sessionStorage.getItem(STORAGE_KEY);
	sessionStorage.setItem(STORAGE_KEY, next);
	if (!prev || prev === next) {
		return;
	}
	const count = payload?.todo_count || (payload?.todos || []).length;
	if (!count || notifyPermission() !== "granted") {
		return;
	}
	try {
		new Notification("Sevamrita", {
			body: count === 1 ? "1 pending action needs you." : `${count} pending actions need you.`,
			tag: "sevamrita-todos",
		});
	} catch (_) {}
}
