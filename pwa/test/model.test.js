import test from "node:test";
import assert from "node:assert/strict";
import {
	pendingWith,
	progressOf,
	trackerState,
	receipt,
	filterTrackers,
	safeFileURL,
	itemPayload,
	newItem,
	queueFailure,
	mergeConversation,
} from "../src/model.js";
const tracker = {
	title: "Kitchen",
	item_kind: "Tracker",
	status: "Open",
	owner: "ravi",
	assignee: "arjun",
	assignee_name: "Arjun",
	item_data: {
		scale: "Status",
		assignment_mode: "Stages",
		stage: "verify",
		stages: [
			{ key: "plan", label: "Plan", assignee: "ravi" },
			{ key: "verify", label: "Verification", assignee: "arjun", assignee_name: "Arjun" },
			{ key: "done", label: "Ready", assignee: "ravi" },
		],
	},
};
test("stage responsibility follows the current stage, not the tracker creator", () => {
	assert.equal(pendingWith(tracker).user, "arjun");
	assert.equal(pendingWith({ ...tracker, status: "Completed" }), null);
	assert.equal(
		pendingWith({ ...tracker, item_data: { ...tracker.item_data, stage: null } }).user,
		"ravi",
	);
});
test("status tracker has proportional dots and current label", () => {
	assert.equal(progressOf(tracker).percent, 50);
	assert.equal(progressOf(tracker).label, "Verification");
	assert.equal(progressOf({ ...tracker, status: "Completed" }).percent, 100);
});
test("percentage and number trackers retain zero as a recorded value", () => {
	assert.equal(
		progressOf({
			item_data: { scale: "Number", minimum: 10, maximum: 110, value: 60, unit: "meals" },
		}).percent,
		50,
	);
	assert.equal(progressOf({ item_data: { scale: "Percentage", value: 0 } }).label, "0%");
	assert.equal(
		progressOf({ item_data: { scale: "Percentage", value: null } }).label,
		"Not started",
	);
});
test("stage positions use configured percentages", () => {
	assert.equal(
		progressOf({
			...tracker,
			item_data: {
				...tracker.item_data,
				scale: "Stages",
				stages: tracker.item_data.stages.map((s, i) => ({
					...s,
					position: [10, 65, 100][i],
				})),
			},
		}).percent,
		65,
	);
});
test("tracker colours distinguish unopened, underway and complete", () => {
	assert.equal(trackerState(tracker), "progress");
	assert.equal(trackerState({ ...tracker, item_data: { scale: "Percentage" } }), "waiting");
	assert.equal(trackerState({ ...tracker, status: "Completed" }), "complete");
});
test("tracker filters exclude closed work from pending categories", () => {
	const rows = [tracker, { ...tracker, name: "done", status: "Completed" }];
	assert.equal(filterTrackers(rows, "My actions", "arjun").length, 1);
	assert.equal(filterTrackers(rows, "Waiting on others", "arjun").length, 0);
	assert.equal(filterTrackers(rows, "Completed", "arjun").length, 1);
	assert.equal(filterTrackers(rows, "All", "arjun").length, 2);
});
test("message receipt needs read and delivery cursors past message creation", () => {
	const e = { creation: "2026-11-08 10:00:00" };
	assert.equal(receipt(e, { receipt_through: { seen_through: "2026-11-08 10:00:01" } }), 3);
	assert.equal(receipt(e, { receipt_through: { delivered_through: "2026-11-08 10:00:01" } }), 2);
	assert.equal(receipt(e, {}), 1);
});
test("private file URLs reject external origins and other ERP paths", () => {
	assert.equal(
		safeFileURL("/private/files/plan.pdf", "https://example.org"),
		"/private/files/plan.pdf",
	);
	for (const s of [
		"https://evil.com/private/files/a",
		"javascript:alert(1)",
		"/desk",
		"/private/files/../../api/method/login",
	])
		assert.equal(safeFileURL(s, "https://example.org"), null);
});
test("new tracker uses Status and no artificial stage names", () => {
	const f = newItem("Tracker", "ravi");
	assert.equal(f.item_data.scale, "Status");
	assert.deepEqual(f.item_data.stages, []);
});
test("payload omits server-managed permission, owner and version fields", () => {
	const payload = itemPayload({ ...tracker, name: "id", modified: "now", can_edit: true });
	assert.equal(payload.name, undefined);
	assert.equal(payload.can_edit, undefined);
	assert.equal(payload.owner, undefined);
	assert.equal(payload.item_data.stage, "verify");
});
test("validation/conflicts require attention while network failures remain queued", () => {
	assert.equal(queueFailure({ status: 417 }), "attention");
	assert.equal(queueFailure({ status: 403 }), "denied");
	assert.equal(queueFailure({ status: 401 }), "auth");
	assert.equal(queueFailure({ status: 503 }), "retry");
	assert.equal(queueFailure({}), "retry");
});

test("quiet refresh preserves already-loaded older message history and next cursor", () => {
	const old = {
		space: { name: "room" },
		entries: [
			{ name: "old", creation: "2026-11-01" },
			{ name: "new", creation: "2026-11-02", body: "before" },
		],
		older_cursor: "old-cursor",
	};
	const incoming = {
		space: { name: "room" },
		entries: [
			{ name: "new", creation: "2026-11-02", body: "edited" },
			{ name: "latest", creation: "2026-11-03" },
		],
		older_cursor: "new-cursor",
	};
	const merged = mergeConversation(old, incoming);
	assert.equal(merged.entries.length, 3);
	assert.equal(merged.entries[1].body, "edited");
	assert.equal(merged.older_cursor, "old-cursor");
});
