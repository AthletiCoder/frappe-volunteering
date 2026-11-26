<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="Expense Claim approval limits"
			eyebrow="Accounts"
			subtitle="Set the largest individual claim each employee grade may approve."
		>
			<template #actions>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<p v-if="error" class="message-error" role="alert">{{ error }}</p>
		<p v-if="message" class="message-success" role="status">{{ message }}</p>
		<p v-if="loading" class="text-muted" role="status">Loading approval limits…</p>

		<template v-else-if="authorized">
			<section class="rounded-2xl border border-line bg-accent-soft p-5 text-sm">
				<strong>Every verified claim follows the reporting hierarchy.</strong>
				<p class="mt-2 text-muted">
					The immediate reporting manager reviews first. If this claim exceeds that
					manager’s limit, they may reject it or escalate it to the next linked manager.
					Unlike advances, only this claim’s amount is tested—not the employee’s other
					claims or outstanding advances.
				</p>
			</section>

			<form class="form-card space-y-5" @submit.prevent="save">
				<div>
					<h2 class="form-title mb-1">Limits by employee grade</h2>
					<p class="form-hint mb-0">
						The current advance/general authority is shown only as a reference.
						Changing an Expense Claim limit does not change advance authority.
					</p>
				</div>

				<div class="space-y-3">
					<div
						v-for="row in rows"
						:key="row.grade"
						class="grid gap-3 rounded-xl border border-line bg-bg p-4 sm:grid-cols-3 sm:items-end"
					>
						<div>
							<span class="text-xs text-muted">Employee grade</span>
							<p class="font-semibold mt-1">{{ row.grade }}</p>
						</div>
						<div>
							<span class="text-xs text-muted">Advance/general authority</span>
							<p class="font-medium mt-1">
								{{
									row.unlimited ? "Unlimited" : money(row.advance_approval_limit)
								}}
							</p>
						</div>
						<label class="field-label mb-0">
							Expense Claim limit
							<span v-if="row.unlimited" class="field-input block bg-soft"
								>Unlimited</span
							>
							<input
								v-else
								v-model.number="row.expense_claim_limit"
								type="number"
								min="0"
								step="0.01"
								required
								class="field-input"
								:aria-label="`${row.grade} Expense Claim limit`"
							/>
						</label>
					</div>
				</div>

				<div class="flex justify-end">
					<button type="submit" class="btn-primary" :disabled="saving">
						{{ saving ? "Saving…" : "Save Expense Claim limits" }}
					</button>
				</div>
			</form>
		</template>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const method = "volunteering.volunteering.expense_approval_limits_portal.";
const loading = ref(true);
const saving = ref(false);
const authorized = ref(false);
const error = ref("");
const message = ref("");
const currency = ref("INR");
const rows = ref([]);

function applyPayload(payload) {
	authorized.value = Boolean(payload?.can_edit);
	currency.value = payload?.currency || "INR";
	rows.value = (payload?.rows || []).map((row) => ({ ...row }));
}

function money(value) {
	return new Intl.NumberFormat("en-IN", {
		style: "currency",
		currency: currency.value,
		maximumFractionDigits: 2,
	}).format(Number(value || 0));
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		applyPayload(await call(method + "get_expense_approval_limits"));
	} catch (err) {
		authorized.value = false;
		error.value = err.message || "Unable to load Expense Claim approval limits.";
	} finally {
		loading.value = false;
	}
}

async function save() {
	saving.value = true;
	error.value = "";
	message.value = "";
	try {
		applyPayload(
			await call(method + "save_expense_approval_limits", {
				rows: rows.value.map(({ grade, expense_claim_limit }) => ({
					grade,
					expense_claim_limit,
				})),
			}),
		);
		message.value = "Expense Claim approval limits saved.";
	} catch (err) {
		error.value = err.message || "Unable to save Expense Claim approval limits.";
	} finally {
		saving.value = false;
	}
}

onMounted(load);
</script>

<style scoped>
</style>
