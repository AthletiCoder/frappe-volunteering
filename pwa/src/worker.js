import { activeAccount, read, write } from "./storage.js";
import { flush } from "./sync.js";

const BASE = "/assets/volunteering/sf_tasks/";
const VERSION = import.meta.url.split("/").pop();
const CACHE = `sf-tasks-shell-${VERSION}`;
self.addEventListener("install", (event) => {
	event.waitUntil(
		(async () => {
			const index = await fetch(BASE + "precache.json", { cache: "no-store" });
			if (!index.ok) throw new Error("Cannot load the offline app.");
			const assets = await index.json();
			if (!assets.every((path) => path.startsWith(BASE) && !path.includes("..")))
				throw new Error("Invalid offline assets.");
			await (
				await caches.open(CACHE)
			).addAll(
				assets.map(
					(path) =>
						new Request(new URL(path, self.location.origin), { cache: "reload" }),
				),
			);
			// First install can activate immediately. Later updates wait for a user-approved reload.
			if (!self.registration.active) await self.skipWaiting();
		})(),
	);
});
self.addEventListener("activate", (event) => {
	event.waitUntil(self.clients.claim());
});
self.addEventListener("message", (event) => {
	if (event.data?.type === "ACTIVATE") self.skipWaiting();
	if (event.data?.type === "CLEAR_OLD_SHELLS")
		event.waitUntil(
			(async () => {
				for (const name of await caches.keys())
					if (name.startsWith("sf-tasks-shell-") && name !== CACHE)
						await caches.delete(name);
			})(),
		);
});
self.addEventListener("fetch", (event) => {
	const url = new URL(event.request.url);
	if (
		event.request.method !== "GET" ||
		url.origin !== self.location.origin ||
		["reload", "no-store"].includes(event.request.cache)
	)
		return;
	// Deliberately never HTTP-cache API calls, login pages, ERP Home or private files.
	if (event.request.mode === "navigate" && url.pathname.startsWith("/sf-tasks/")) {
		event.respondWith(
			(async () =>
				(await caches.open(CACHE))
					.match(BASE + "index.html")
					.then((cached) => cached || fetch(event.request)))(),
		);
	} else if (url.pathname.startsWith(BASE) && !url.pathname.endsWith("precache.json")) {
		event.respondWith(
			(async () =>
				(await (await caches.open(CACHE)).match(event.request)) || fetch(event.request))(),
		);
	}
});
async function sync() {
	const user = await activeAccount();
	if (user)
		await flush(user, async () => {
			for (const client of await self.clients.matchAll())
				client.postMessage({ type: "OUTBOX_CHANGED" });
		});
}
self.addEventListener("sync", (event) => {
	if (event.tag === "sf-tasks-outbox") event.waitUntil(sync());
});
self.addEventListener("push", (event) => {
	event.waitUntil(
		(async () => {
			// Notification payload contains routing IDs only. Content stays inside authenticated ERP APIs.
			let payload;
			try {
				payload = event.data.json();
			} catch {
				return;
			}
			const user = await activeAccount();
			if (!user || payload.binding !== (await read(user, "push-binding"))) return;
			const windows = await self.clients.matchAll({
				type: "window",
				includeUncontrolled: false,
			});
			for (const client of windows)
				if (client.visibilityState === "visible")
					client.postMessage({ type: "PUSH_REFRESH" });
			if (
				payload.kind === "message" &&
				windows.some((client) => {
					const url = new URL(client.url);
					return (
						client.visibilityState === "visible" &&
						url.searchParams.get("space") === payload.space &&
						!url.searchParams.get("item") &&
						(!url.searchParams.get("tab") || url.searchParams.get("tab") === "Chat")
					);
				})
			)
				return;
			const settings = (await read(user, "settings")) || {};
			const mode = settings.chats?.[payload.space] || settings.notifications;
			if (mode === "Mute") return;
			if (
				payload.kind === "message" &&
				mode === "Mentions" &&
				!payload.mentioned &&
				!payload.assigned
			)
				return;
			const stamp = `notice:${payload.key}`;
			if (await read(user, stamp)) return;
			await self.registration.showNotification(
				payload.kind === "reminder"
					? "SF Tasks reminder"
					: payload.mentioned
						? "You were mentioned in SF Tasks"
						: "New activity in SF Tasks",
				{
					body: "Open SF Tasks to view it.",
					icon: BASE + "icon-192.png",
					badge: BASE + "icon-192.png",
					tag: `sf-tasks:${payload.space || payload.item || "updates"}`,
					renotify: false,
					data: { space: payload.space, item: payload.item },
				},
			);
			await write(user, stamp, Date.now());
		})(),
	);
});
self.addEventListener("notificationclick", (event) => {
	event.notification.close();
	event.waitUntil(
		(async () => {
			const url = new URL("/sf-tasks/", self.location.origin),
				data = event.notification.data || {};
			if (data.space) url.searchParams.set("space", data.space);
			if (data.item) url.searchParams.set("item", data.item);
			const windows = await self.clients.matchAll({ type: "window" });
			const client = windows.find((client) =>
				new URL(client.url).pathname.startsWith("/sf-tasks/"),
			);
			if (client) {
				try {
					// Bring the Android app forward before navigation replaces its window client.
					const focused = await client.focus();
					if (focused.url === url.href || (await focused.navigate(url.href))) return;
				} catch {
					// The existing window may have closed or could not be activated.
				}
			}
			return self.clients.openWindow(url.href);
		})(),
	);
});
