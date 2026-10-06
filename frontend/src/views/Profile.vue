<template>
	<div class="space-y-5">
		<PageHeader
			title="My profile"
			subtitle="Your details recorded with Sevamrita."
			eyebrow="Employee"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>
		<p v-if="loading" class="text-muted" role="status">Loading your profile…</p>
		<p v-else-if="error" class="text-bad" role="alert">{{ error }}</p>
		<template v-else-if="profile">
			<p class="text-sm text-muted">
				Login and employment details are read-only. Contact your administrator if a correction is needed.
			</p>
			<template v-for="(section, index) in sections" :key="section.title">
				<section class="rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-6">
					<h2 class="mb-4 text-lg font-semibold text-ink">{{ section.title }}</h2>
					<dl class="grid grid-cols-1 gap-x-6 gap-y-5 sm:grid-cols-2">
						<div v-for="field in section.fields" :key="field.label" class="min-w-0">
							<dt class="text-sm text-muted">{{ field.label }}</dt>
							<dd class="mt-1 break-words whitespace-pre-wrap font-medium text-ink">{{ field.value || "Not set" }}</dd>
						</div>
					</dl>
				</section>
				<section v-if="index === 0 && profile.employee" class="rounded-2xl border border-line bg-surface p-5 shadow-soft sm:p-6">
					<div class="flex flex-wrap items-start justify-between gap-3">
						<div><h2 class="text-lg font-semibold text-ink">Reimbursement bank account</h2><p class="mt-1 text-sm text-muted">Only Accounts Manager-approved details can be used for bank reimbursement.</p></div>
						<RouterLink to="/bank-account" class="btn-secondary">{{ bankSummary?.approved ? "Manage bank details" : "Add bank details" }}</RouterLink>
					</div>
					<p v-if="bankError" class="mt-4 rounded-xl bg-bad-soft p-3 text-sm text-bad" role="alert">{{ bankError }}</p>
					<template v-else-if="bankSummary?.approved">
						<dl class="mt-5 grid grid-cols-1 gap-x-6 gap-y-5 border-t border-line pt-5 sm:grid-cols-2 lg:grid-cols-3">
							<div v-for="field in approvedBankFields" :key="field.label" class="min-w-0">
								<dt class="text-sm text-muted">{{ field.label }}</dt>
								<dd class="mt-1 break-words font-medium text-ink">{{ field.value || "Not set" }}</dd>
							</div>
						</dl>
						<p v-if="bankSummary.pending" class="mt-5 rounded-xl bg-warn-soft p-3 text-sm text-ink">A replacement bank account is awaiting Accounts Manager approval. The approved account above remains active until then.</p>
					</template>
					<p v-else-if="bankSummary?.pending" class="mt-4 rounded-xl bg-warn-soft p-3 text-sm text-ink">{{ bankSummary.pending.bank_name }} · {{ bankSummary.pending.account_number_masked }} is awaiting Accounts Manager approval.</p>
					<p v-else class="mt-4 text-sm text-muted">No approved reimbursement bank account is on file.</p>
				</section>
			</template>
			<p
				v-if="!profile.employee"
				class="rounded-xl border border-line bg-surface p-4 text-sm text-muted"
			>
				No Employee record is linked to your login yet. Contact your administrator to link
				it.
			</p>
		</template>
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
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

const sections = computed(() => {
	if (!profile.value) return [];
	const { account, employee: e } = profile.value;
	const result = [
		{
			title: "Login details",
			fields: [
				field("Name", account.full_name),
				field("User ID", account.user_id),
				field("Login email", account.email),
				field("Account type", account.user_type),
			],
		},
	];
	if (!e) return result;
	result.push(
		{
			title: "Employment details",
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
			fields: [
				field("Reporting manager", e.reporting_manager_name || e.reports_to),
				field("Expense approver", e.expense_approver_name || e.expense_approver),
			],
		},
		{
			title: "Contact details",
			fields: [
				field("Mobile number", e.cell_number),
				field("Work email", e.company_email),
				field("Personal email", e.personal_email),
			],
		},
		{
			title: "Emergency contact",
			fields: [
				field("Contact person", e.person_to_be_contacted),
				field("Relationship", e.relation),
				field("Contact number", e.emergency_phone_number),
			],
		},
	);
	return result;
});
const approvedBankFields = computed(() => {
	const account = bankSummary.value?.approved;
	if (!account) return [];
	return [
		field("Account holder", account.account_holder_name),
		field("Bank", account.bank_name),
		field("Branch", account.branch),
		field("Account number", account.account_number_masked),
		field("IFSC", account.ifsc),
		field("Account type", account.account_type),
		field("Approved on", formatDate(account.reviewed_on)),
	];
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
