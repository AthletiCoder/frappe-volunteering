<template>
	<div class="space-y-5">
		<PageHeader title="My profile" subtitle="Your details recorded with Sevamrita." eyebrow="Employee">
			<template #actions>
				<RouterLink to="/home" class="btn-back">Back to Home</RouterLink>
			</template>
		</PageHeader>
		<div v-if="loading" class="space-y-4" aria-busy="true">
			<p class="sr-only" role="status">Loading your profile…</p>
			<div class="skeleton h-44 rounded-[20px]"></div>
			<div class="grid gap-5 lg:grid-cols-[minmax(0,1fr)_22rem]"><div class="skeleton h-80 rounded-2xl"></div><div class="skeleton h-80 rounded-2xl"></div></div>
		</div>
		<p v-else-if="error" class="message-error" role="alert">{{ error }}</p>
		<template v-else-if="profile">
			<!-- Identity band -->
			<div class="profile-hero">
				<img :src="'/assets/volunteering/brand/lotus-mark.png'" alt="" class="profile-hero__lotus" width="220" height="186" />
				<div class="relative flex min-w-0 flex-wrap items-center gap-4 sm:gap-5">
					<span class="profile-avatar" aria-hidden="true">{{ initials }}</span>
					<div class="min-w-0">
						<h2 class="profile-hero__name">{{ displayName }}</h2>
						<p v-if="roleLine" class="mt-0.5 text-sm text-white/75">{{ roleLine }}</p>
						<div class="mt-3 flex flex-wrap gap-2">
							<span v-if="employee?.status" class="hero-chip hero-chip--ok"><span class="h-1.5 w-1.5 rounded-full bg-current"></span>{{ employee.status }}</span>
							<span v-if="employee?.employment_type" class="hero-chip">{{ employee.employment_type }}</span>
							<span v-if="employee?.branch" class="hero-chip"><Icon name="map-pin" size="sm" />{{ employee.branch }}</span>
						</div>
					</div>
				</div>
				<dl v-if="employee" class="profile-hero__facts">
					<div><dt>Joined</dt><dd>{{ niceDate(employee.date_of_joining) || "Not set" }}</dd></div>
					<div v-if="tenure"><dt>With us</dt><dd>{{ tenure }}</dd></div>
					<div v-if="employee.reporting_manager_name || employee.reports_to"><dt>Reports to</dt><dd>{{ employee.reporting_manager_name || employee.reports_to }}</dd></div>
				</dl>
			</div>

			<p class="flex items-start gap-2 text-sm text-muted"><Icon name="help" size="sm" class="mt-0.5 text-muted" />Login and employment details are read-only. Contact your administrator if a correction is needed.</p>

			<div class="profile-board">
				<div class="min-w-0 space-y-5">
					<section v-for="section in mainSections" :key="section.title" class="kit-panel p-5 sm:p-6">
						<div class="mb-4 flex items-center gap-3">
							<span class="section-icon"><Icon :name="section.icon" size="sm" /></span>
							<h2 class="text-base font-semibold text-ink">{{ section.title }}</h2>
						</div>
						<!-- Reporting line drawn as a chain -->
						<div v-if="section.chain" class="chain">
							<div v-for="(person, i) in section.chain" :key="person.role" class="chain__row">
								<span class="chain__rail" :class="{ 'chain__rail--last': i === section.chain.length - 1 }" aria-hidden="true"></span>
								<Avatar :name="person.value || '?'" :tone="person.self ? 'navy' : 'slate'" />
								<div class="min-w-0">
									<p class="text-xs text-muted">{{ person.role }}</p>
									<p v-if="person.value" class="truncate text-sm font-semibold text-ink">{{ person.value }}</p>
									<p v-else class="not-set">Not set</p>
								</div>
							</div>
						</div>
						<dl v-else class="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2">
							<div v-for="item in section.fields" :key="item.label" class="field-row">
								<dt class="text-xs font-medium text-muted">{{ item.label }}</dt>
								<dd v-if="item.value" class="mt-1 whitespace-pre-wrap break-words text-sm font-medium text-ink">{{ item.value }}</dd>
								<dd v-else class="not-set mt-1">Not set</dd>
							</div>
						</dl>
					</section>
					<p v-if="!profile.employee" class="kit-panel p-4 text-sm text-muted">No Employee record is linked to your login yet. Contact your administrator to link it.</p>
				</div>

				<aside class="min-w-0 space-y-5">
					<!-- Completeness -->
					<section v-if="profile.employee" class="kit-panel p-5" aria-labelledby="completeness-title">
						<div class="flex items-center gap-4">
							<svg class="h-16 w-16 shrink-0 -rotate-90" viewBox="0 0 36 36" aria-hidden="true">
								<circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--soft)" stroke-width="4" />
								<circle cx="18" cy="18" r="15.5" fill="none" :stroke="completeness === 100 ? 'var(--ok)' : 'var(--marigold)'" stroke-width="4" stroke-linecap="round" :stroke-dasharray="`${(completeness / 100) * 97.4} 97.4`" class="transition-[stroke-dasharray] duration-500" />
							</svg>
							<div class="min-w-0">
								<h2 id="completeness-title" class="text-base font-semibold text-ink">Profile {{ completeness }}% complete</h2>
								<p class="text-xs text-muted">{{ missing.length ? `${missing.length} ${missing.length === 1 ? "detail is" : "details are"} not on file` : "Everything is on file." }}</p>
							</div>
						</div>
						<ul v-if="missing.length" class="mt-4 flex flex-wrap gap-1.5">
							<li v-for="item in missing" :key="item" class="chip bg-marigold-soft text-[#7a4a00]">{{ item }}</li>
						</ul>
						<p v-if="missing.length" class="mt-3 text-xs leading-relaxed text-muted">Ask HR to add these to your employee record.</p>
					</section>

					<!-- Bank account -->
					<section v-if="profile.employee" class="kit-panel p-5" aria-labelledby="bank-title">
						<div class="flex flex-wrap items-start justify-between gap-3">
							<div><h2 id="bank-title" class="text-base font-semibold text-ink">Reimbursement bank account</h2><p class="mt-1 text-xs leading-relaxed text-muted">Only Accounts Manager-approved details can be used for bank reimbursement.</p></div>
						</div>
						<p v-if="bankError" class="mt-4 rounded-xl bg-bad-soft p-3 text-sm text-bad" role="alert">{{ bankError }}</p>
						<template v-else-if="bankSummary?.approved">
							<div class="bank-card mt-4">
								<div class="flex items-start justify-between gap-3">
									<span class="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/60">{{ bankSummary.approved.account_type || "Account" }}</span>
									<Icon name="bank" class="text-marigold" />
								</div>
								<p class="mt-5 font-mono text-lg tracking-[0.14em]">{{ bankSummary.approved.account_number_masked }}</p>
								<div class="mt-4 flex items-end justify-between gap-3 text-xs">
									<div class="min-w-0"><p class="text-white/55">Holder</p><p class="truncate font-semibold">{{ bankSummary.approved.account_holder_name }}</p></div>
									<div class="text-right"><p class="text-white/55">IFSC</p><p class="font-semibold tracking-wide">{{ bankSummary.approved.ifsc }}</p></div>
								</div>
							</div>
							<dl class="mt-4 grid grid-cols-2 gap-3 text-sm">
								<div v-for="item in approvedBankFields" :key="item.label" class="min-w-0"><dt class="text-xs text-muted">{{ item.label }}</dt><dd v-if="item.value" class="mt-0.5 break-words font-medium text-ink">{{ item.value }}</dd><dd v-else class="not-set mt-0.5">Not set</dd></div>
							</dl>
							<p v-if="bankSummary.pending" class="mt-4 rounded-xl bg-warn-soft p-3 text-sm text-ink">A replacement bank account is awaiting Accounts Manager approval. The approved account above remains active until then.</p>
						</template>
						<p v-else-if="bankSummary?.pending" class="mt-4 rounded-xl bg-warn-soft p-3 text-sm text-ink">{{ bankSummary.pending.bank_name }} · {{ bankSummary.pending.account_number_masked }} is awaiting Accounts Manager approval.</p>
						<div v-else class="mt-4 flex items-center gap-3 rounded-xl border border-dashed border-line-strong p-4 text-sm text-muted"><Icon name="bank" class="text-muted" />No approved reimbursement bank account is on file.</div>
						<RouterLink to="/bank-account" class="btn-secondary mt-4 w-full">{{ bankSummary?.approved ? "Manage bank details" : "Add bank details" }}</RouterLink>
					</section>

					<!-- Login -->
					<section class="kit-panel p-5">
						<div class="mb-4 flex items-center gap-3"><span class="section-icon"><Icon name="user-shield" size="sm" /></span><h2 class="text-base font-semibold text-ink">Login details</h2></div>
						<dl class="space-y-3">
							<div v-for="item in loginFields" :key="item.label" class="min-w-0"><dt class="text-xs font-medium text-muted">{{ item.label }}</dt><dd v-if="item.value" class="mt-0.5 break-words text-sm font-medium text-ink">{{ item.value }}</dd><dd v-else class="not-set mt-0.5">Not set</dd></div>
						</dl>
					</section>
				</aside>
			</div>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import Avatar from "../components/Avatar.vue";
import Icon from "../components/Icon.vue";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const loading = ref(true);
const error = ref("");
const profile = ref(null);
const bankSummary = ref(null);
const bankError = ref("");
const field = (label, value) => ({ label, value });
function formatDate(value) {
	if (!value) return "";
	const parts = String(value).slice(0, 10).split("-");
	return parts.length === 3 ? `${parts[2]}-${parts[1]}-${parts[0]}` : value;
}
function niceDate(value) {
	if (!value) return "";
	const date = new Date(`${String(value).slice(0, 10)}T12:00:00`);
	return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", year: "numeric" }).format(date);
}

const employee = computed(() => profile.value?.employee || null);
const displayName = computed(() => employee.value?.employee_name || profile.value?.account?.full_name || "");
const initials = computed(() => {
	const words = String(displayName.value).replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
	return (words.slice(0, 2).map((word) => word[0]).join("") || "•").toUpperCase();
});
const roleLine = computed(() => [employee.value?.designation, employee.value?.grade].filter(Boolean).join(" · "));
const tenure = computed(() => {
	const raw = employee.value?.date_of_joining;
	if (!raw) return "";
	const start = new Date(`${String(raw).slice(0, 10)}T12:00:00`);
	if (Number.isNaN(start.getTime())) return "";
	const now = new Date();
	let months = (now.getFullYear() - start.getFullYear()) * 12 + (now.getMonth() - start.getMonth());
	if (now.getDate() < start.getDate()) months -= 1;
	if (months < 1) return "New this month";
	const years = Math.floor(months / 12), rest = months % 12;
	return [years ? `${years} yr${years === 1 ? "" : "s"}` : "", rest ? `${rest} mo` : ""].filter(Boolean).join(" ");
});

const loginFields = computed(() => {
	const account = profile.value?.account || {};
	return [field("Name", account.full_name), field("User ID", account.user_id), field("Login email", account.email), field("Account type", account.user_type)];
});

const mainSections = computed(() => {
	const e = employee.value;
	if (!e) return [];
	return [
		{
			title: "Employment details",
			icon: "clipboard-check",
			fields: [
				field("Employee name", e.employee_name),
				field("Employee ID", e.name),
				field("Status", e.status),
				field("Joining date", formatDate(e.date_of_joining)),
				field("Designation", e.designation),
				field("Grade", e.grade),
				field("Employment type", e.employment_type),
				field("Branch", e.branch),
			],
		},
		{
			title: "Reporting and approvals",
			icon: "people",
			chain: [
				{ role: "Reporting manager", value: e.reporting_manager_name || e.reports_to },
				{ role: "You", value: e.employee_name, self: true },
				{ role: "Expense approver", value: e.expense_approver_name || e.expense_approver },
			],
		},
		{
			title: "Contact details",
			icon: "chat",
			fields: [field("Mobile number", e.cell_number), field("Work email", e.company_email), field("Personal email", e.personal_email)],
		},
		{
			title: "Emergency contact",
			icon: "user-shield",
			fields: [field("Contact person", e.person_to_be_contacted), field("Relationship", e.relation), field("Contact number", e.emergency_phone_number)],
		},
	];
});

// Completeness counts only details a person would expect HR to hold for them.
const completenessFields = computed(() => {
	const e = employee.value;
	if (!e) return [];
	return [
		["Designation", e.designation], ["Grade", e.grade], ["Employment type", e.employment_type], ["Branch", e.branch],
		["Joining date", e.date_of_joining], ["Reporting manager", e.reporting_manager_name || e.reports_to],
		["Expense approver", e.expense_approver_name || e.expense_approver], ["Mobile number", e.cell_number],
		["Work email", e.company_email], ["Personal email", e.personal_email],
		["Emergency contact", e.person_to_be_contacted], ["Emergency number", e.emergency_phone_number],
	];
});
const missing = computed(() => completenessFields.value.filter(([, value]) => !value).map(([label]) => label));
const completeness = computed(() => {
	const total = completenessFields.value.length;
	return total ? Math.round(((total - missing.value.length) / total) * 100) : 0;
});

const approvedBankFields = computed(() => {
	const account = bankSummary.value?.approved;
	if (!account) return [];
	return [field("Bank", account.bank_name), field("Branch", account.branch), field("Approved on", formatDate(account.reviewed_on))];
});

onMounted(async () => {
	try {
		profile.value = await call("volunteering.volunteering.employee_profile.get_my_profile");
		if (profile.value?.employee) {
			try {
				bankSummary.value = await call("volunteering.volunteering.employee_bank_accounts.get_my_bank_account_summary");
			} catch (err) {
				bankError.value = err.message || "Unable to load your bank details.";
			}
		}
	} catch (err) {
		error.value = err.message || "Unable to load your profile.";
	} finally {
		loading.value = false;
	}
});
</script>

<style scoped>
.profile-hero {
	position: relative;
	display: flex;
	flex-wrap: wrap;
	align-items: flex-end;
	justify-content: space-between;
	gap: 1.25rem 2rem;
	overflow: hidden;
	padding: 1.5rem 1.25rem;
	border-radius: 20px;
	color: #fff;
	background:
		radial-gradient(120% 140% at 100% 0%, rgb(242 181 68 / 0.16), transparent 46%),
		radial-gradient(90% 120% at 0% 100%, rgb(27 63 120 / 0.9), transparent 60%),
		linear-gradient(135deg, var(--navy-900), var(--navy-800));
	box-shadow: 0 18px 40px -22px rgb(5 34 77 / 0.55);
}
@media (min-width: 768px) {
	.profile-hero { padding: 1.75rem 2rem; }
}
.profile-hero__lotus {
	position: absolute;
	right: -1.5rem;
	bottom: -2.5rem;
	width: 13.75rem;
	height: auto;
	opacity: 0.07;
	filter: brightness(0) invert(1);
	pointer-events: none;
}
.profile-avatar {
	display: inline-flex;
	width: 4.5rem;
	height: 4.5rem;
	flex-shrink: 0;
	align-items: center;
	justify-content: center;
	border-radius: 999px;
	background: linear-gradient(135deg, #fff, var(--navy-100));
	color: var(--navy-900);
	font-family: theme("fontFamily.display");
	font-size: 1.5rem;
	font-weight: 600;
	box-shadow: 0 0 0 3px var(--marigold), 0 0 0 7px rgb(242 181 68 / 0.18);
}
.profile-hero__name {
	font-size: clamp(1.375rem, 1.1rem + 0.9vw, 1.75rem);
	font-weight: 600;
	line-height: 1.15;
	color: #fff;
}
.hero-chip {
	display: inline-flex;
	align-items: center;
	gap: 0.375rem;
	border-radius: 999px;
	padding: 0.1875rem 0.625rem;
	background: rgb(255 255 255 / 0.1);
	box-shadow: inset 0 0 0 1px rgb(255 255 255 / 0.16);
	font-size: 0.75rem;
	font-weight: 600;
	color: rgb(255 255 255 / 0.88);
}
.hero-chip--ok { color: #b6f0cf; }
.profile-hero__facts {
	position: relative;
	display: flex;
	flex-wrap: wrap;
	gap: 0.75rem 2rem;
}
.profile-hero__facts dt {
	font-size: 0.6875rem;
	font-weight: 600;
	letter-spacing: 0.08em;
	text-transform: uppercase;
	color: rgb(255 255 255 / 0.55);
}
.profile-hero__facts dd {
	margin-top: 0.125rem;
	font-size: 0.9375rem;
	font-weight: 600;
	color: #fff;
}

.profile-board {
	display: grid;
	gap: 1.25rem;
	align-items: start;
}
@media (min-width: 1024px) {
	.profile-board { grid-template-columns: minmax(0, 1fr) 22rem; gap: 1.5rem; }
}
.section-icon {
	display: inline-flex;
	width: 2rem;
	height: 2rem;
	flex-shrink: 0;
	align-items: center;
	justify-content: center;
	border-radius: 10px;
	background: var(--navy-50);
	color: var(--navy-900);
}
.field-row {
	min-width: 0;
	padding-bottom: 0.875rem;
	border-bottom: 1px solid var(--line);
}
.not-set {
	display: inline-flex;
	align-items: center;
	gap: 0.25rem;
	border-radius: 6px;
	padding: 0.0625rem 0.4375rem;
	background: var(--soft);
	font-size: 0.75rem;
	font-weight: 500;
	font-style: italic;
	color: var(--muted);
}

.chain { display: grid; gap: 0; }
.chain__row {
	position: relative;
	display: flex;
	align-items: center;
	gap: 0.875rem;
	padding: 0.5rem 0;
}
.chain__rail {
	position: absolute;
	left: 1.125rem;
	top: 2.25rem;
	bottom: -0.5rem;
	width: 2px;
	background: var(--line);
	transform: translateX(-1px);
}
.chain__rail--last { display: none; }

.bank-card {
	position: relative;
	overflow: hidden;
	border-radius: 16px;
	padding: 1.125rem 1.25rem;
	color: #fff;
	background:
		radial-gradient(120% 140% at 100% 0%, rgb(242 181 68 / 0.22), transparent 50%),
		linear-gradient(135deg, var(--navy-900), var(--navy-600));
	box-shadow: 0 14px 30px -18px rgb(5 34 77 / 0.7);
}
</style>
