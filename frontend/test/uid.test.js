import { test } from "node:test";
import assert from "node:assert/strict";
import { uid } from "../src/lib/uid.js";

const V4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test("uid falls back to a v4 id when randomUUID is unavailable (plain-http sites)", () => {
	const original = globalThis.crypto.randomUUID;
	try {
		Object.defineProperty(globalThis.crypto, "randomUUID", { value: undefined, configurable: true });
		const ids = new Set(Array.from({ length: 200 }, uid));
		assert.equal(ids.size, 200);
		for (const id of ids) assert.match(id, V4);
	} finally {
		Object.defineProperty(globalThis.crypto, "randomUUID", { value: original, configurable: true });
	}
});

test("uid uses randomUUID when present", () => {
	assert.match(uid(), V4);
});
