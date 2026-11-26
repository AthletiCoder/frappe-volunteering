// Step lists for the shared ProgressTracker. Each step has a label, a state
// (done | current | attention | stopped | todo) and an optional note.

function build(labels, currentIndex, overrides = {}) {
	return labels.map((label, index) => ({
		label,
		state: index < currentIndex ? "done" : index === currentIndex ? "current" : "todo",
		...(overrides[index] || {}),
	}));
}

// Expense claim stages come from expense_claim_portal._claim_stage.
const CLAIM_STEPS = ["Submitted", "Receipt review", "Manager approval", "Accounts", "Paid"];
const CLAIM_STAGE_INDEX = {
	Draft: 0,
	"Receipt review": 1,
	"Needs correction": 1,
	"Manager approval": 2,
	"Accounts classification": 3,
	"Approved / unpaid": 4,
	Paid: 5,
};
// Workflow states recorded in the claim's history, mapped to the step they belong to.
const CLAIM_STATE_INDEX = {
	"Pending Receipt Review": 1,
	"Receipt Correction Required": 1,
	"Pending Approval": 2,
	"Pending Accounts Classification": 3,
	Approved: 4,
};

export function claimSteps(stage, timeline = [], pendingWith = "") {
	if (["Rejected", "Withdrawn", "Cancelled"].includes(stage)) {
		// Stop at the step the claim had reached, as recorded in its history.
		const reached = Math.max(1, ...timeline.map((event) => CLAIM_STATE_INDEX[event.label] ?? 0));
		return build(CLAIM_STEPS.slice(0, reached + 1), reached, { [reached]: { state: "stopped", note: stage } });
	}
	const index = CLAIM_STAGE_INDEX[stage] ?? 0;
	if (stage === "Draft") return build(CLAIM_STEPS, 0, { 0: { label: "Draft", state: "attention", note: "Not sent yet" } });
	if (stage === "Needs correction") return build(CLAIM_STEPS, 1, { 1: { state: "attention", note: "Needs your correction" } });
	const note = pendingWith ? `With ${pendingWith}` : stage === "Approved / unpaid" ? "Awaiting payment" : "";
	return build(CLAIM_STEPS, index, index < CLAIM_STEPS.length ? { [index]: { note } } : {});
}

// Leave, WFH and attendance requests: Open → decided.
export function timeRequestSteps(status) {
	const labels = ["Submitted", "Decision"];
	if (status === "Approved") return build([...labels.slice(0, 1), "Approved"], 2);
	if (status === "Rejected" || status === "Cancelled") return build([...labels.slice(0, 1), status], 1, { 1: { state: "stopped" } });
	return build(labels, 1, { 1: { note: "Waiting for a decision" } });
}

// Purchase orders: request → approval → delivery → supplier bill → payment.
export function purchaseSteps(order) {
	const labels = ["Requested", "Approved", "Received", "Billed", "Paid"];
	const state = order?.workflow_state || "Draft";
	if (state === "Rejected") return build(labels.slice(0, 2), 1, { 1: { state: "stopped", note: "Rejected" } });
	if (state === "Draft") return build(labels, 0, { 0: { label: "Draft", state: "attention", note: "Not sent yet" } });
	if (state !== "Approved") return build(labels, 1, { 1: { note: order?.pending_approver ? `With ${order.pending_approver}` : "Awaiting approval" } });
	const received = Number(order.per_received || 0);
	const billed = Number(order.per_billed || 0);
	const invoices = order.invoices || [];
	const outstanding = invoices.reduce((sum, row) => sum + Number(row.outstanding_amount || 0), 0);
	if (received < 100) return build(labels, 2, { 2: { note: received ? `${Math.round(received)}% received` : "Awaiting delivery" } });
	if (billed < 100) return build(labels, 3, { 3: { note: billed ? `${Math.round(billed)}% billed` : "Awaiting supplier bill" } });
	if (!invoices.length || outstanding > 0) return build(labels, 4, { 4: { note: "Awaiting payment" } });
	return build(labels, 5);
}
