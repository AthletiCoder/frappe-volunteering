<template>
	<section
		v-if="visible"
		class="rounded-2xl border border-line bg-surface shadow-soft p-4 mb-6"
	>
		<h2 class="text-lg font-semibold text-ink">Request from manager float</h2>
		<p class="text-sm text-muted mt-1">
			Submit an expense claim that settles from your reporting manager's paid advance after approval — no
			bank reimbursement to you.
		</p>

		<div v-if="error" class="text-bad text-sm mt-3">{{ error }}</div>

		<div v-else-if="loading" class="text-muted text-sm mt-3">Loading manager options…</div>

		<template v-else-if="context">
			<div v-if="!context.can_request" class="text-warn text-sm mt-3">
				No reporting manager on your employee record. Ask HR to set Reports To, or use Out of Pocket
				reimbursement in Desk.
			</div>

			<template v-else>
				<div class="mt-3 grid gap-2 md:grid-cols-3">
					<div class="rounded-xl bg-soft p-3">
						<div class="text-xs text-muted">Manager</div>
						<div class="font-semibold text-ink">{{ context.manager_name || context.manager_employee }}</div>
					</div>
					<div class="rounded-xl bg-soft p-3">
						<div class="text-xs text-muted">Float available</div>
						<div class="font-semibold text-ink">{{ formatMoney(context.total_residual) }}</div>
					</div>
					<div class="rounded-xl bg-soft p-3">
						<div class="text-xs text-muted">Paid advances</div>
						<div class="font-semibold text-ink">{{ (context.fundable_advances || []).length }}</div>
					</div>
				</div>

				<p class="text-sm text-muted mt-3">
					<span v-if="context.total_residual > 0">
						Your manager can Approve when the claim amount fits their residual. If not, they Escalate.
					</span>
					<span v-else class="text-warn">
						Your manager has no paid advance with residual. They must get an advance paid before approving
						this type of claim.
					</span>
				</p>

				<div class="mt-4 flex flex-wrap gap-2">
					<a class="btn-primary text-sm" :href="newClaimUrl">New claim (manager float)</a>
					<a class="btn-secondary text-sm" href="/desk/expense-claim/new">New claim (out of pocket)</a>
				</div>
			</template>
		</template>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { call } from "../lib/frappe";
import { formatMoney } from "../lib/money";

const context = ref(null);
const loading = ref(false);
const error = ref("");
const loaded = ref(false);

const newClaimUrl = computed(() => {
	const base = "/desk/expense-claim/new";
	const params = new URLSearchParams({ reimbursement_source: "Manager Advance" });
	return `${base}?${params.toString()}`;
});

/** Hide entirely when the employee still has their own unsettled advance. */
const visible = computed(() => {
	if (!loaded.value) return false;
	if (context.value?.own_blocking_advance) return false;
	return true;
});

async function load() {
	loading.value = true;
	error.value = "";
	try {
		context.value = await call("volunteering.volunteering.manager_float_service.get_manager_float_context");
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
		loaded.value = true;
	}
}

onMounted(load);
</script>
