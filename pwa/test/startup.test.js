import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const source = readFileSync(new URL("../src/App.vue", import.meta.url), "utf8");
const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
// Execute the component's actual startup functions with a controlled session and store.
function componentFunction(name, nextName, context) {
	const start = source.indexOf(`async function ${name}(`);
	const end = source.indexOf(`async function ${nextName}(`, start);
	assert.ok(start >= 0 && end > start);
	return new Function(...Object.keys(context), `return (${source.slice(start, end).trim()})`)(
		...Object.values(context),
	);
}
const ref = (value) => ({ value });

test("startup paints saved content without a POST before authenticating, then refreshes", async () => {
	const calls = [];
	let authenticated = false;
	const context = {
		store: {
			activeAccount: async () => "ravi",
			read: async () => ({ full_name: "Ravi" }),
			activate: async () => {},
			write: async () => {},
			clearSnapshots: async () => {},
		},
		user: ref(null),
		allowed: ref(false),
		fullName: ref(""),
		authExpired: ref(false),
		restore: async () => calls.push("restore"),
		loadRoute: async ({ cacheOnly = false } = {}) => {
			calls.push(cacheOnly ? "cached route" : "network route");
			if (!cacheOnly)
				assert.ok(authenticated, "network route must wait for the CSRF session");
		},
		session: async () => {
			calls.push("session");
			authenticated = true;
			return { user: "ravi", full_name: "Ravi", allowed: true };
		},
		refresh: async () => calls.push("refresh"),
		syncNow: async () => calls.push("sync"),
	};
	await componentFunction("boot", "restore", context)();
	assert.deepEqual(calls, [
		"restore",
		"cached route",
		"session",
		"restore",
		"network route",
		"refresh",
		"sync",
	]);
});

test("offline startup restores saved content without attempting authenticated operations", async () => {
	const routes = [];
	const context = {
		store: { activeAccount: async () => "ravi", read: async () => ({ full_name: "Ravi" }) },
		user: ref(null),
		allowed: ref(false),
		fullName: ref(""),
		authExpired: ref(false),
		restore: async () => {},
		loadRoute: async (options) => routes.push(options),
		session: async () => {
			throw new TypeError("Failed to fetch");
		},
		refresh: async () => assert.fail("must not refresh offline"),
		syncNow: async () => assert.fail("must not submit offline"),
	};
	await componentFunction("boot", "restore", context)();
	assert.ok(routes.length);
	assert.ok(routes.every((options) => options?.cacheOnly));
	assert.equal(context.user.value, "ravi");
});

function routeContext(route) {
	return {
		activeView: 0,
		selected: ref(null),
		itemOnly: ref(false),
		room: ref(null),
		roomTab: ref(""),
		detailTab: ref(""),
		user: ref("ravi"),
		allowed: ref(true),
		route: ref(route),
		roomId: ref(route.space),
		online: ref(true),
		view: ref("chats"),
		thread: ref(null),
		nextTick: async () => {},
		restoreDraft: async () => {},
		guarded: async (action) => action(),
		fetchItemView: async () => assert.fail("must not fetch an item before session"),
		refreshRoom: async () => assert.fail("must not fetch a room before session"),
		loadMentions: async () => assert.fail("must not fetch mentions before session"),
		loadQueue: async () => {},
		store: {
			read: async (_account, key) =>
				key.startsWith("item-view:")
					? { item_only: false, items: [{ name: "tracker" }] }
					: key.startsWith("item:")
						? { name: "tracker" }
						: { entries: [] },
		},
	};
}

test("cached tracker deep link restores details while deferring its network request", async () => {
	const context = routeContext({ item: "tracker", space: "kitchen" });
	await componentFunction("loadRoute", "fetchItemView", context)({ cacheOnly: true });
	assert.equal(context.selected.value.name, "tracker");
	assert.equal(context.room.value.item_only, false);
});

test("cached chat deep link restores its saved conversation while deferring network requests", async () => {
	const context = routeContext({ space: "kitchen" });
	await componentFunction("loadRoute", "fetchItemView", context)({ cacheOnly: true });
	assert.deepEqual(context.room.value.entries, []);
});
