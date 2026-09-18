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
				These details are read-only. Contact your administrator if a correction is needed.
			</p>
			<section
				v-for="section in sections"
				:key="section.title"
				class="rounded-2xl border border-line bg-surface p-5 sm:p-6 shadow-soft"
			>
				<h2 class="text-lg font-semibold text-ink mb-4">{{ section.title }}</h2>
				<dl class="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-5">
					<div v-for="field in section.fields" :key="field.label" class="min-w-0">
						<dt class="text-sm text-muted">{{ field.label }}</dt>
						<dd class="mt-1 font-medium text-ink break-words whitespace-pre-wrap">
							{{ field.value || "Not set" }}
						</dd>
					</div>
				</dl>
			</section>
			<p
				v-if="!profile.employee"
				class="rounded-xl border border-line bg-surface p-4 text-sm text-muted"
			>
				No Employee record is linked to your login yet. Contact your administrator to link
				it.
			</p>
			<RouterLink v-if="profile.employee" to="/bank-account" class="btn-secondary"
				>Reimbursement bank details</RouterLink
			>
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

onMounted(async () => {
	try {
		profile.value = await call("volunteering.volunteering.employee_profile.get_my_profile");
	} catch (err) {
		error.value = err.message || "Unable to load your profile.";
	} finally {
		loading.value = false;
	}
});
</script>
