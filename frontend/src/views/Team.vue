<template>
	<div>
		<PageHeader
			eyebrow="People"
			title="My team"
			subtitle="Direct-report context for day-to-day supervision. Salary, bank, receipt and ledger details stay private."
		>
			<template #actions>
				<button class="btn-secondary" type="button" :disabled="loading" @click="load">
					{{ loading ? "Loading…" : "Refresh" }}
				</button>
			</template>
		</PageHeader>

		<p v-if="error" class="rounded-xl bg-bad-soft p-3 text-sm text-bad mb-4" role="alert">
			{{ error }}
		</p>
		<div v-if="loading && !team.length" class="text-muted py-10 text-center">
			Loading your team…
		</div>

		<section class="grid gap-4">
			<article
				v-for="person in team"
				:key="person.employee"
				class="rounded-2xl border border-line bg-surface shadow-soft overflow-hidden"
			>
				<header
					class="p-4 sm:p-5 flex flex-wrap justify-between gap-3 border-b border-line"
				>
					<div>
						<div class="flex flex-wrap items-center gap-2">
							<h2 class="text-lg font-semibold text-ink">
								{{ person.employee_name }}
							</h2>
							<span class="status-pill">{{ person.employee }}</span>
							<span
								v-if="person.advance_control.frozen"
								class="rounded-full bg-bad-soft px-2 py-0.5 text-xs font-semibold text-bad"
								>Advances frozen</span
							>
						</div>
						<p class="text-sm text-muted mt-1">
							{{ person.designation || "No designation" }}
							<span v-if="person.grade"> · {{ person.grade }}</span>
							<span v-if="person.department"> · {{ person.department }}</span>
						</p>
					</div>
					<div class="text-sm sm:text-right">
						<p class="text-muted">Today</p>
						<p class="font-semibold text-ink">{{ person.attendance.today.status }}</p>
						<p v-if="person.attendance.today.working_hours" class="text-xs text-muted">
							{{ person.attendance.today.working_hours }} hours recorded
						</p>
					</div>
				</header>

				<div class="p-4 sm:p-5 grid gap-5 lg:grid-cols-2">
					<section>
						<h3 class="section-title">Attendance and requests</h3>
						<div class="flex flex-wrap gap-2 mt-2">
							<span
								v-for="(count, status) in person.attendance.month"
								:key="status"
								class="metric-chip"
								>{{ status }}: {{ count }}</span
							>
							<span
								v-if="!Object.keys(person.attendance.month).length"
								class="text-sm text-muted"
								>No attendance marked this month.</span
							>
						</div>
						<div class="grid grid-cols-3 gap-2 mt-3 text-center">
							<div class="mini-stat">
								<strong>{{ person.requests.leave_pending }}</strong
								><span>Leave pending</span>
							</div>
							<div class="mini-stat">
								<strong>{{ person.requests.wfh_pending }}</strong
								><span>WFH pending</span>
							</div>
							<div class="mini-stat">
								<strong>{{ person.requests.attendance_fixes_pending }}</strong
								><span>Fixes pending</span>
							</div>
						</div>
					</section>

					<section>
						<h3 class="section-title">Projects</h3>
						<div v-if="person.projects.length" class="flex flex-wrap gap-2 mt-2">
							<span
								v-for="project in person.projects"
								:key="project.name"
								class="metric-chip"
							>
								{{ project.project_name || project.name }} ·
								{{ project.operational_status }}
							</span>
						</div>
						<p v-else class="text-sm text-muted mt-2">
							No current project membership.
						</p>
					</section>
				</div>

				<details class="border-t border-line group" :open="person.advances.length > 0">
					<summary
						class="cursor-pointer list-none p-4 sm:px-5 flex justify-between gap-3"
					>
						<span class="font-semibold text-ink">Advances</span>
						<span class="text-sm text-muted">{{ person.advances.length }} recent</span>
					</summary>
					<div class="px-4 sm:px-5 pb-5">
						<div v-if="!person.advances.length" class="text-sm text-muted">
							No advances.
						</div>
						<div
							v-for="advance in person.advances"
							:key="advance.name"
							class="grid gap-2 border-t border-line py-3 sm:grid-cols-[1fr_auto]"
						>
							<div>
								<a
									:href="advance.route"
									class="font-medium text-accent hover:underline"
									>{{ advance.name }}</a
								>
								<p class="text-sm text-muted">{{ advance.purpose || "—" }}</p>
								<p v-if="advance.intended_project" class="text-xs text-muted">
									Project: {{ advance.intended_project }}
								</p>
							</div>
							<div class="sm:text-right text-sm">
								<p class="font-medium">
									{{ advance.workflow_state || advance.status }}
								</p>
								<p class="text-muted">
									{{ money(advance.advance_amount) }} requested ·
									{{ money(advance.residual) }} open
								</p>
							</div>
						</div>
					</div>
				</details>

				<section class="border-t border-line p-4 sm:p-5 bg-soft/40">
					<div v-if="person.advance_control.frozen" class="text-sm mb-3">
						<p class="font-medium text-bad">New advance requests are frozen.</p>
						<p class="text-muted">
							{{ person.advance_control.reason }}
							<span v-if="person.advance_control.acted_on">
								· {{ dateTime(person.advance_control.acted_on) }}</span
							>
						</p>
					</div>
					<label class="block text-sm font-medium text-ink">
						{{
							person.advance_control.frozen
								? "Reason to unfreeze"
								: "Reason to freeze new advances"
						}}
						<textarea
							v-model.trim="reasons[person.employee]"
							rows="2"
							maxlength="500"
							class="field-input mt-1"
							placeholder="Required for the audit history"
						></textarea>
					</label>
					<div class="flex justify-end mt-2">
						<button
							type="button"
							:class="
								person.advance_control.frozen ? 'btn-secondary' : 'btn-primary'
							"
							:disabled="saving === person.employee || !reasons[person.employee]"
							@click="changeFreeze(person)"
						>
							{{
								saving === person.employee
									? "Saving…"
									: person.advance_control.frozen
										? "Unfreeze advances"
										: "Freeze new advances"
							}}
						</button>
					</div>
				</section>
			</article>
		</section>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";
import { formatMoney } from "../lib/money";

const API = "volunteering.volunteering.team_portal.";
const team = ref([]);
const loading = ref(false);
const saving = ref("");
const error = ref("");
const reasons = reactive({});

function money(value) {
	return formatMoney(value || 0);
}

function dateTime(value) {
	return value ? new Date(value.replace(" ", "T")).toLocaleString() : "";
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		const result = await call(`${API}get_team_dashboard`);
		team.value = result?.team || [];
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}

async function changeFreeze(person) {
	const reason = reasons[person.employee];
	if (!reason || saving.value) return;
	saving.value = person.employee;
	error.value = "";
	try {
		person.advance_control = await call(
			"volunteering.volunteering.advance_freeze.set_advance_freeze",
			{
				employee: person.employee,
				frozen: person.advance_control.frozen ? 0 : 1,
				reason,
			},
		);
		reasons[person.employee] = "";
	} catch (e) {
		error.value = e.message || String(e);
		window.scrollTo({ top: 0, behavior: "smooth" });
	} finally {
		saving.value = "";
	}
}

onMounted(load);
</script>

<style scoped>
.status-pill,
.metric-chip {
	@apply rounded-full bg-soft px-2.5 py-1 text-xs text-muted;
}
.section-title {
	@apply text-sm font-semibold text-ink;
}
.mini-stat {
	@apply rounded-xl border border-line bg-surface p-2;
}
.mini-stat strong,
.mini-stat span {
	@apply block;
}
.mini-stat span {
	@apply mt-0.5 text-[11px] text-muted;
}
.field-input {
	@apply block w-full rounded-xl border border-line bg-surface px-3 py-2.5 text-sm text-ink;
}
.field-input:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
</style>
