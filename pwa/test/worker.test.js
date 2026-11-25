import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { runInNewContext } from "node:vm";
function worker(clients = {}) {
	const handlers = {},
		cached = [],
		shown = [],
		records = new Map();
	const env = {
		URL,
		Request,
		console,
		fetch: async () =>
			Response.json([
				"/assets/volunteering/sf_tasks/index.html",
				"/assets/volunteering/sf_tasks/assets/app-new.js",
			]),
		self: {
			location: { origin: "https://example.org" },
			registration: { active: {}, showNotification: async (...args) => shown.push(args) },
			clients: { claim: async () => {}, matchAll: async () => [], ...clients },
			addEventListener: (name, handler) => (handlers[name] = handler),
			skipWaiting: async () => {},
		},
		caches: {
			open: async () => ({
				addAll: async (paths) => cached.push(...paths),
				match: async (url) =>
					url === "/assets/volunteering/sf_tasks/index.html"
						? new Response("offline shell")
						: null,
			}),
			keys: async () => ["sf-tasks-shell-old"],
			delete: async () => {
				throw new Error("Do not delete older tabs’ code during activation");
			},
		},
		activeAccount: async () => "ravi",
		read: async (user, key) => records.get(key),
		write: async (user, key, value) => records.set(key, value),
		flush: async () => {},
	};
	const source = readFileSync(new URL("../src/worker.js", import.meta.url), "utf8")
		.replace(/^import .*;\n/gm, "")
		.replaceAll(
			"import.meta.url",
			JSON.stringify(
				"https://example.org/assets/volunteering/sf_tasks/assets/worker-hash.js?v=release-1",
			),
		);
	runInNewContext(source, env);
	return { handlers, cached, shown, records };
}
async function waitEvent(handler, event) {
	let promise;
	handler({ ...event, waitUntil: (p) => (promise = p) });
	await promise;
}
test("offline installation precaches only the separate PWA assets", async () => {
	const w = worker();
	await waitEvent(w.handlers.install, {});
	assert.equal(w.cached.length, 2);
	assert.ok(
		w.cached.every(
			(p) =>
				new URL(p.url).pathname.startsWith("/assets/volunteering/sf_tasks/") &&
				p.cache === "reload",
		),
	);
});
test("service worker never intercepts ERP Home, APIs, login or private receipts", () => {
	const w = worker();
	for (const path of [
		"/volunteering/home",
		"/desk",
		"/api/method/login",
		"/private/files/receipt.pdf",
	]) {
		let intercepted = false;
		w.handlers.fetch({
			request: { url: "https://example.org" + path, method: "GET", mode: "navigate" },
			respondWith: () => (intercepted = true),
		});
		assert.equal(intercepted, false, path);
	}
});
test("offline navigation returns a public shell rather than cached private HTML", async () => {
	const w = worker();
	let response;
	w.handlers.fetch({
		request: {
			url: "https://example.org/sf-tasks/?space=private",
			method: "GET",
			mode: "navigate",
		},
		respondWith: (p) => (response = p),
	});
	assert.equal(await (await response).text(), "offline shell");
});
test("activation preserves assets for older open tabs", async () => {
	const w = worker();
	await waitEvent(w.handlers.activate, {});
});
test("notification for an old account binding is ignored", async () => {
	const w = worker();
	w.records.set("push-binding", "current");
	await waitEvent(w.handlers.push, {
		data: { json: () => ({ binding: "prior", key: "a", space: "chat" }) },
	});
	assert.equal(w.shown.length, 0);
});
test("replayed push shows one generic notification without exposing message content", async () => {
	const w = worker();
	w.records.set("push-binding", "current");
	const event = {
		data: {
			json: () => ({
				binding: "current",
				key: "once",
				kind: "message",
				space: "chat",
				body: "must not leak",
			}),
		},
	};
	await waitEvent(w.handlers.push, event);
	await waitEvent(w.handlers.push, event);
	assert.equal(w.shown.length, 1);
	assert.equal(w.shown[0][1].body, "Open SF Tasks to view it.");
	assert.ok(!JSON.stringify(w.shown).includes("must not leak"));
});
test("muted notifications are suppressed on the device", async () => {
	const w = worker();
	w.records.set("push-binding", "current");
	w.records.set("settings", { notifications: "Mute" });
	await waitEvent(w.handlers.push, {
		data: { json: () => ({ binding: "current", key: "mute", space: "chat" }) },
	});
	assert.equal(w.shown.length, 0);
});
test("conversation override can allow activity when general notifications are muted", async () => {
	const w = worker();
	w.records.set("push-binding", "current");
	w.records.set("settings", { notifications: "Mute", chats: { chat: "All" } });
	await waitEvent(w.handlers.push, {
		data: {
			json: () => ({ binding: "current", key: "override", kind: "message", space: "chat" }),
		},
	});
	assert.equal(w.shown.length, 1);
});
test("a cache-bypassing build request is never answered from an old shell", () => {
	const w = worker();
	let intercepted = false;
	w.handlers.fetch({
		request: {
			url: "https://example.org/assets/volunteering/sf_tasks/index.html",
			method: "GET",
			mode: "same-origin",
			cache: "reload",
		},
		respondWith: () => (intercepted = true),
	});
	assert.equal(intercepted, false);
});

test("notification focuses the app before changing conversation", async () => {
	const home = "https://example.org/sf-tasks/";
	const destination = home + "?space=chat&item=task";
	const steps = [];
	const window = {
		url: home,
		focus: async () => {
			steps.push("focus");
			return {
				url: home,
				navigate: async (url) => {
					steps.push(url);
					return { url };
				},
			};
		},
		navigate: async () => assert.fail("the unfocused Android window must not navigate"),
	};
	const w = worker({
		matchAll: async () => [window],
		openWindow: async () => assert.fail("reuse the app"),
	});
	await waitEvent(w.handlers.notificationclick, {
		notification: { data: { space: "chat", item: "task" }, close: () => {} },
	});
	assert.deepEqual(steps, ["focus", destination]);
});

test("notification opens its deep link when the existing window cannot be focused", async () => {
	const opened = [];
	const w = worker({
		matchAll: async () => [
			{
				url: "https://example.org/sf-tasks/",
				focus: async () => {
					throw new Error("Window closed");
				},
			},
		],
		openWindow: async (url) => opened.push(url),
	});
	await waitEvent(w.handlers.notificationclick, {
		notification: { data: { space: "chat" }, close: () => {} },
	});
	assert.deepEqual(opened, ["https://example.org/sf-tasks/?space=chat"]);
});

test("notification opens the target on a cold launch", async () => {
	const opened = [];
	const w = worker({ openWindow: async (url) => opened.push(url) });
	await waitEvent(w.handlers.notificationclick, {
		notification: { data: { space: "chat" }, close: () => {} },
	});
	assert.deepEqual(opened, ["https://example.org/sf-tasks/?space=chat"]);
});
