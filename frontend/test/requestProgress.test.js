import assert from "node:assert/strict";
import test from "node:test";
import { claimSteps, purchaseSteps, timeRequestSteps } from "../src/lib/requestProgress.js";

const states = (steps) => steps.map((step) => `${step.label}:${step.state}`);

test("claim steps follow the employee-facing stage", () => {
	assert.deepEqual(states(claimSteps("Receipt review")), ["Submitted:done", "Receipt review:current", "Manager approval:todo", "Accounts:todo", "Paid:todo"]);
	assert.deepEqual(states(claimSteps("Approved / unpaid")).slice(-2), ["Accounts:done", "Paid:current"]);
	assert.ok(claimSteps("Paid").every((step) => step.state === "done"));
	assert.equal(claimSteps("Needs correction")[1].state, "attention");
	assert.equal(claimSteps("Manager approval", [], "Asha")[2].note, "With Asha");
});

test("stopped claims end at the step they had reached", () => {
	const history = [{ label: "Claim created" }, { label: "Pending Receipt Review" }, { label: "Pending Approval" }, { label: "Rejected" }];
	assert.deepEqual(states(claimSteps("Rejected", history)), ["Submitted:done", "Receipt review:done", "Manager approval:stopped"]);
	assert.deepEqual(states(claimSteps("Withdrawn", [{ label: "Claim created" }])), ["Submitted:done", "Receipt review:stopped"]);
});

test("time requests and purchase orders", () => {
	assert.deepEqual(states(timeRequestSteps("Open")), ["Submitted:done", "Decision:current"]);
	assert.deepEqual(states(timeRequestSteps("Approved")), ["Submitted:done", "Approved:done"]);
	assert.deepEqual(states(timeRequestSteps("Rejected")), ["Submitted:done", "Rejected:stopped"]);
	assert.equal(purchaseSteps({ workflow_state: "Pending Approval" })[1].state, "current");
	assert.equal(purchaseSteps({ workflow_state: "Approved", per_received: 40 })[2].note, "40% received");
	assert.equal(purchaseSteps({ workflow_state: "Approved", per_received: 100, per_billed: 100, invoices: [{ outstanding_amount: 50 }] })[4].state, "current");
	assert.ok(purchaseSteps({ workflow_state: "Approved", per_received: 100, per_billed: 100, invoices: [{ outstanding_amount: 0 }] }).every((step) => step.state === "done"));
});
