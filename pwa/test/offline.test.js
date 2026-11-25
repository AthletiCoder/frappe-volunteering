import "fake-indexeddb/auto";
import test from "node:test";
import assert from "node:assert/strict";
import * as storage from "../src/storage.js";
import { flush } from "../src/sync.js";
const ravi = "offline-ravi@example.com",
	arjun = "offline-arjun@example.com";
await storage.activate(ravi);
let serverUser = ravi,
	operations = 0,
	failStatus = 0;
globalThis.fetch = async (url, options) => {
	if (url.endsWith("get_session"))
		return Response.json({
			message: { user: serverUser, allowed: true, csrf_token: "test-csrf" },
		});
	operations++;
	return failStatus
		? Response.json(
				{
					_server_messages: JSON.stringify([
						JSON.stringify({ message: "Record changed" }),
					]),
				},
				{ status: failStatus },
			)
		: Response.json({ message: { name: "sent" } });
};

test("private snapshots are encrypted with an account-specific non-exportable key", async () => {
	await storage.write(ravi, "room:test", { body: "private kitchen details" });
	const db = await storage.database();
	const raw = await new Promise((resolve, reject) => {
		const r = db.transaction("records").objectStore("records").get(`${ravi}:room:test`);
		r.onsuccess = () => resolve(r.result);
		r.onerror = reject;
	});
	assert.ok(raw.data instanceof ArrayBuffer);
	assert.ok(!new TextDecoder().decode(raw.data).includes("private kitchen"));
	assert.deepEqual(await storage.read(ravi, "room:test"), { body: "private kitchen details" });
	assert.equal(await storage.read(arjun, "room:test"), null);
});
test("draft survives reopening and cannot be retrieved under another account", async () => {
	await storage.write(ravi, "draft:room", "Draft before restart");
	await storage.activate(arjun);
	assert.equal(await storage.read(arjun, "draft:room"), null);
	await storage.activate(ravi);
	assert.equal(await storage.read(ravi, "draft:room"), "Draft before restart");
});
test("message queue and clearing its draft are committed together", async () => {
	await storage.write(ravi, "draft:room", "Send this");
	const row = await storage.enqueue(
		ravi,
		"send_message",
		{ payload: { space: "room", body: "Send this" } },
		"draft:room",
	);
	assert.equal(await storage.read(ravi, "draft:room"), "");
	assert.equal((await storage.outbox(ravi))[0].id, row.id);
	await storage.remove(ravi, `queue:${row.id}`);
});
test("queue retries use the same request key and remove only after server success", async () => {
	const row = await storage.enqueue(ravi, "send_message", {
		payload: { space: "room", body: "Retry safely" },
	});
	failStatus = 503;
	await assert.rejects(flush(ravi));
	assert.equal((await storage.outbox(ravi))[0].id, row.id);
	failStatus = 0;
	await flush(ravi);
	assert.equal((await storage.outbox(ravi)).length, 0);
});
test("version conflicts are preserved for review and do not retry automatically", async () => {
	const row = await storage.enqueue(ravi, "update_task", { name: "task", action: "start" });
	failStatus = 417;
	await flush(ravi);
	assert.equal((await storage.outbox(ravi))[0].status, "attention");
	const count = operations;
	await flush(ravi);
	assert.equal(operations, count);
	await storage.remove(ravi, `queue:${row.id}`);
	failStatus = 0;
});
test("a different server account cannot send the prior account’s Outbox", async () => {
	const row = await storage.enqueue(ravi, "update_task", { name: "task", action: "start" });
	serverUser = arjun;
	const count = operations;
	await assert.rejects(flush(ravi));
	assert.equal(operations, count);
	assert.equal((await storage.outbox(ravi)).length, 1);
	await storage.remove(ravi, `queue:${row.id}`);
	serverUser = ravi;
});
test("concurrent page and worker queue flushes hold one account lease", async () => {
	await storage.enqueue(ravi, "send_message", { payload: { space: "room", body: "One send" } });
	const count = operations;
	await Promise.all([flush(ravi), flush(ravi), flush(ravi)]);
	assert.equal(operations - count, 1);
});
test("forgetting an account clears its data and key without touching another account", async () => {
	await storage.activate(arjun);
	await storage.write(arjun, "room:kept", { body: "Arjun data" });
	await storage.activate(ravi);
	await storage.forget(ravi);
	assert.equal(await storage.activeAccount(), null);
	assert.equal(await storage.read(ravi, "draft:room"), null);
	assert.deepEqual(await storage.read(arjun, "room:kept"), { body: "Arjun data" });
});
test("known access revocation removes item-view snapshots as well as room content", async () => {
	await storage.activate(arjun);
	await storage.write(arjun, "item-view:private", { space: { members: ["hidden"] } });
	await storage.write(arjun, "room:private", { entries: ["private"] });
	await storage.clearSnapshots(arjun);
	assert.equal(await storage.read(arjun, "item-view:private"), null);
	assert.equal(await storage.read(arjun, "room:private"), null);
});

test("durable mutation carries the original account as an atomic server-side guard", async () => {
	await storage.activate(arjun);
	serverUser = arjun;
	let submitted;
	const original = globalThis.fetch;
	globalThis.fetch = async (url, options) => {
		if (url.endsWith("apply_operation")) submitted = JSON.parse(options.body);
		return original(url, options);
	};
	await storage.enqueue(arjun, "send_message", {
		payload: { space: "room", body: "Account guard" },
	});
	await flush(arjun);
	globalThis.fetch = original;
	assert.equal(submitted.expected_user, arjun);
});
