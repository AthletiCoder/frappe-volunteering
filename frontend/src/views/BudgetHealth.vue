<template>
	<div>
		<div class="flex items-center justify-between mb-6">
			<div>
				<h1 class="text-2xl font-bold text-gray-900">Budget Health</h1>
				<p class="text-sm text-gray-500">Department utilisation across projects</p>
			</div>
			<button
				class="px-3 py-1.5 rounded-lg bg-gray-900 text-white text-sm"
				@click="load"
				:disabled="loading"
			>
				{{ loading ? "Loading…" : "Refresh" }}
			</button>
		</div>

		<div v-if="error" class="text-red-600 mb-4">{{ error }}</div>

		<div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
			<div v-for="card in summaryCards" :key="card.label" class="rounded-xl border bg-white p-4 shadow-sm">
				<div class="text-xs text-gray-500">{{ card.label }}</div>
				<div class="text-xl font-bold mt-1" :style="{ color: card.color }">{{ card.value }}</div>
			</div>
		</div>

		<div class="rounded-xl border bg-white shadow-sm overflow-hidden">
			<table class="w-full text-sm">
				<thead class="bg-gray-50 text-left text-gray-600">
					<tr>
						<th class="px-3 py-2">Project</th>
						<th class="px-3 py-2">Type</th>
						<th class="px-3 py-2">Status</th>
						<th class="px-3 py-2">Department</th>
						<th class="px-3 py-2 text-right">Allocated</th>
						<th class="px-3 py-2 text-right">Consumed</th>
						<th class="px-3 py-2 text-right">Remaining</th>
						<th class="px-3 py-2">Health</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="row in rows" :key="row.project + row.department" class="border-t">
						<td class="px-3 py-2">
							<a class="text-blue-700 hover:underline" :href="row.route">{{ row.project }}</a>
						</td>
						<td class="px-3 py-2">{{ row.project_type || "—" }}</td>
						<td class="px-3 py-2">
							<span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="pillClass(row)">
								{{ row.budget_status || "Active" }}
							</span>
						</td>
						<td class="px-3 py-2">
							<a
								v-if="row.department"
								class="text-blue-700 hover:underline"
								:href="`/app/department/${encodeURIComponent(row.department)}`"
								>{{ row.department }}</a
							>
						</td>
						<td class="px-3 py-2 text-right">{{ formatMoney(row.allocated) }}</td>
						<td class="px-3 py-2 text-right">{{ formatMoney(row.consumed) }}</td>
						<td class="px-3 py-2 text-right">{{ formatMoney(row.remaining) }}</td>
						<td class="px-3 py-2 min-w-[140px]">
							<span class="px-2 py-0.5 rounded-full text-xs font-semibold" :class="pillClass(row)">
								{{ Math.round(row.utilisation_pct || 0) }}%
							</span>
							<div class="mt-1 h-2 rounded-full bg-gray-100 overflow-hidden">
								<div
									class="h-full rounded-full"
									:style="{
										width: Math.min(row.utilisation_pct || 0, 100) + '%',
										background: barColor(row.utilisation_pct),
									}"
								/>
							</div>
						</td>
					</tr>
					<tr v-if="!rows.length && !loading">
						<td colspan="8" class="px-3 py-8 text-center text-gray-500">
							No department budgets configured yet.
						</td>
					</tr>
				</tbody>
			</table>
		</div>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { call } from "../lib/frappe";

const rows = ref([]);
const loading = ref(false);
const error = ref("");

const summaryCards = computed(() => {
	const alloc = rows.value.reduce((s, r) => s + (r.allocated || 0), 0);
	const used = rows.value.reduce((s, r) => s + (r.consumed || 0), 0);
	const warn = rows.value.filter((r) => (r.utilisation_pct || 0) >= 80 && (r.utilisation_pct || 0) < 100).length;
	const over = rows.value.filter((r) => (r.utilisation_pct || 0) >= 100).length;
	return [
		{ label: "Allocated", value: formatMoney(alloc), color: "#111827" },
		{ label: "Consumed", value: formatMoney(used), color: "#111827" },
		{ label: "At risk (≥80%)", value: String(warn), color: "#ca8a04" },
		{ label: "Overspent", value: String(over), color: "#dc2626" },
	];
});

function formatMoney(v) {
	return new Intl.NumberFormat(undefined, { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(
		v || 0
	);
}

function pillClass(row) {
	const pct = row.utilisation_pct || 0;
	if (row.budget_status === "Exhausted" || row.budget_status === "Closed" || pct >= 100)
		return "bg-red-100 text-red-700";
	if (pct >= 80) return "bg-yellow-100 text-yellow-800";
	return "bg-green-100 text-green-700";
}

function barColor(pct) {
	if ((pct || 0) >= 100) return "var(--bad)";
	if ((pct || 0) >= 80) return "var(--warn)";
	return "var(--ok)";
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		rows.value = (await call("volunteering.volunteering.budget_service.get_budget_health")) || [];
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

onMounted(load);
</script>
