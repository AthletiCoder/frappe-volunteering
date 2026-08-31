const STORAGE_KEY = "volunteering.todo.fingerprint";
const PREF_KEY = "volunteering.notify.prefs";

export function todoFingerprint(payload) {
	const todos = payload?.todos || [];
	return todos
		.map((row) => row.id)
		.sort()
		.join("|");
}

function isSecureNotifyContext() {
	if (typeof window === "undefined") return false;
	// Notification API requires a secure context (HTTPS or localhost).
	if (window.isSecureContext) return true;
	const host = window.location.hostname;
	return host === "localhost" || host === "127.0.0.1";
}

export async function requestNotifyPermission() {
	if (typeof Notification === "undefined") {
		return "unsupported";
	}
	if (!isSecureNotifyContext()) {
		return "insecure";
	}
	if (Notification.permission === "granted") {
		return "granted";
	}
	try {
		return await Notification.requestPermission();
	} catch (_) {
		return "unsupported";
	}
}

export function notifyPermission() {
	if (typeof Notification === "undefined") {
		return "unsupported";
	}
	if (!isSecureNotifyContext()) {
		return "insecure";
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

/** @returns {Promise<{ work_log_reminder_opt_in: boolean, org_enabled: boolean, reminder_hour: number }>} */
export async function loadNotificationPreferences() {
	const { call } = await import("./frappe");
	const prefs = await call("volunteering.volunteering.api.work_log_reminder.get_notification_preferences");
	try {
		sessionStorage.setItem(PREF_KEY, JSON.stringify(prefs));
	} catch (_) {}
	return prefs;
}

export function cachedNotificationPreferences() {
	try {
		const raw = sessionStorage.getItem(PREF_KEY);
		return raw ? JSON.parse(raw) : null;
	} catch (_) {
		return null;
	}
}

export async function setWorkLogReminderOptIn(enabled) {
	const { call } = await import("./frappe");
	const prefs = await call("volunteering.volunteering.api.work_log_reminder.set_notification_preferences", {
		work_log_reminder_opt_in: enabled ? 1 : 0,
	});
	try {
		sessionStorage.setItem(PREF_KEY, JSON.stringify(prefs));
	} catch (_) {}
	return prefs;
}
