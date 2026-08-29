<template>
	<section v-if="requests.length || fundable.length" class="rounded-2xl border border-line bg-surface shadow-soft p-4 mb-6">
		<div class="flex justify-between gap-3 flex-wrap items-start">
			<div>
				<h2 class="text-lg font-semibold text-ink">Team reimbursement requests</h2>
				<p class="text-sm text-muted mt-1">
					Reportees asked to settle from your advance float. Approve when you have residual; otherwise Escalate.
				</p>
			</div>
			<span v-if="fundable.length" class="text-sm text-muted">
				Your float: {{ formatMoney(totalResidual) }} across {{ fundable.length }} advance(s)
			</span>
		</div>

		<div v-if="error" class="text-bad text-sm mt-3">{{ error }}</div>
		<div v-else-if="loading" class="text-muted text-sm mt-3">Loading team requests…</div>

		<div v-else-if="!requests.length" class="text-muted text-sm mt-3">No pending manager-float claims from your team.</div>

		<div v-for="req in requests" :key="req.name" class="mt-4 rounded-xl border border-line p-3">
			<div class="flex justify-between gap-3 flex-wrap">
				<div>
					<a class="font-semibold text-accent hover:underline" :href="req.route">{{ req.name }}</a>
					<div class="text-sm text-muted">
						{{ req.employee_name || req.employee }} · {{ formatMoney(req.amount) }}
						<span v-if="req.project"> · {{ req.project }}</span>
					</div>
				</div>
				<span
					class="px-2 py-0.5 rounded-full text-xs font-semibold h-fit"
					:class="req.can_fund ? 'bg-ok-soft text-ok' : 'bg-warn-soft text-warn'"
				>
					{{ req.can_fund ? "Can fund" : "Escalate" }}
				</span>
			</div>
			<p class="text-sm text-muted mt-2">{{ req.funding_message }}</p>
			<a class="btn-primary text-sm mt-2 inline-flex" :href="req.route">Review in Desk</a>
		</div>
	</section>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { call } from "../lib/frappe";
import { formatMoney } from "../lib/money";

const requests = ref([]);
const fundable = ref([]);
const loading = ref(false);
const error = ref("");

const totalResidual = computed(() =>
	(fundable.value || []).reduce((sum, row) => sum + Number(row.residual || 0), 0),
);

async function load() {
	loading.value = true;
	error.value = "";
	try {
		const data = await call("volunteering.volunteering.manager_float_service.get_team_manager_float_requests");
		requests.value = (data && data.requests) || [];
		fundable.value = (data && data.fundable_advances) || [];
	} catch (e) {
		// Managers without reportees may hit empty state; hide section quietly.
		if (!String(e.message || e).includes("not linked")) {
			error.value = e.message || String(e);
		}
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
