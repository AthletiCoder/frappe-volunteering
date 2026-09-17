<template>
	<div class="max-w-5xl mx-auto space-y-5">
		<PageHeader
			title="Office addresses"
			:subtitle="`Current locations recorded for ${workspace.company || 'Sevamrita Foundation'}.`"
			eyebrow="Organisation"
		>
			<template #actions>
				<button
					v-if="workspace.can_manage"
					type="button"
					class="btn-primary"
					@click="beginAdd"
				>
					Add office address
				</button>
				<RouterLink to="/home" class="btn-secondary">Back to Home</RouterLink>
			</template>
		</PageHeader>

		<div v-if="loading" class="text-muted">Loading office addresses…</div>
		<div
			v-if="error"
			class="rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad"
			role="alert"
		>
			{{ error }}
		</div>

		<section v-if="!loading && editing" class="form-card">
			<div class="flex items-center justify-between gap-3 mb-4">
				<div>
					<h2 class="form-title mb-0">
						{{ form.name ? "Edit office address" : "Add office address" }}
					</h2>
					<p class="text-sm text-muted">
						Only Accounts Managers and Administrator can save changes.
					</p>
				</div>
				<button type="button" class="btn-secondary" @click="cancelEdit">Cancel</button>
			</div>
			<form class="form-grid" @submit.prevent="save">
				<label class="field-label"
					>Address title *<input
						v-model.trim="form.address_title"
						required
						maxlength="160"
						class="field-input"
						placeholder="Mumbai office"
				/></label>
				<label class="field-label"
					>Address type *<select
						v-model="form.address_type"
						required
						class="field-input"
					>
						<option v-for="type in workspace.address_types" :key="type">
							{{ type }}
						</option>
					</select></label
				>
				<label class="field-label sm:col-span-2"
					>Address line 1 *<input
						v-model.trim="form.address_line1"
						required
						maxlength="240"
						class="field-input"
				/></label>
				<label class="field-label sm:col-span-2"
					>Address line 2<input
						v-model.trim="form.address_line2"
						maxlength="240"
						class="field-input"
				/></label>
				<label class="field-label"
					>City/Town *<input
						v-model.trim="form.city"
						required
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>District/County<input
						v-model.trim="form.county"
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>State/Province<input
						v-model.trim="form.state"
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>Postal code<input
						v-model.trim="form.pincode"
						maxlength="20"
						class="field-input"
				/></label>
				<label class="field-label"
					>Country *<input
						v-model.trim="form.country"
						required
						maxlength="140"
						class="field-input"
				/></label>
				<label class="field-label"
					>Phone<input v-model.trim="form.phone" maxlength="40" class="field-input"
				/></label>
				<label class="field-label sm:col-span-2"
					>Email address<input
						v-model.trim="form.email_id"
						type="email"
						maxlength="140"
						class="field-input"
				/></label>
				<div class="sm:col-span-2 flex flex-wrap gap-5 text-sm">
					<label class="flex items-center gap-2"
						><input v-model="form.is_primary_address" type="checkbox" />Preferred
						billing address</label
					>
					<label class="flex items-center gap-2"
						><input v-model="form.is_shipping_address" type="checkbox" />Preferred
						shipping address</label
					>
					<label class="flex items-center gap-2"
						><input v-model="form.disabled" type="checkbox" />Disabled</label
					>
				</div>
				<div class="sm:col-span-2 flex justify-end">
					<button type="submit" class="btn-primary" :disabled="saving">
						{{ saving ? "Saving…" : "Save address" }}
					</button>
				</div>
			</form>
		</section>

		<section v-if="!loading" class="space-y-3" aria-label="Office address list">
			<div
				v-if="!workspace.addresses.length"
				class="rounded-2xl border border-line bg-surface p-6 text-center text-muted"
			>
				No office addresses have been recorded yet.
			</div>
			<article
				v-for="address in workspace.addresses"
				:key="address.name"
				class="rounded-2xl border border-line bg-surface p-4 shadow-soft"
			>
				<div class="flex items-start justify-between gap-4">
					<div>
						<div class="flex flex-wrap items-center gap-2">
							<h2 class="font-semibold text-ink">{{ address.address_title }}</h2>
							<span class="badge">{{ address.address_type }}</span>
							<span v-if="address.disabled" class="badge">Disabled</span>
						</div>
						<address class="not-italic text-sm text-muted mt-2 leading-6">
							{{ address.address_line1
							}}<template v-if="address.address_line2"
								><br />{{ address.address_line2 }}</template
							><br />
							{{ locality(address)
							}}<template v-if="address.pincode"> — {{ address.pincode }}</template
							><br />{{ address.country }}
						</address>
						<div
							v-if="address.phone || address.email_id"
							class="text-sm mt-2 space-x-3"
						>
							<span v-if="address.phone">{{ address.phone }}</span
							><span v-if="address.email_id">{{ address.email_id }}</span>
						</div>
						<div class="flex flex-wrap gap-2 mt-3 text-xs">
							<span v-if="address.is_primary_address" class="badge"
								>Preferred billing</span
							><span v-if="address.is_shipping_address" class="badge"
								>Preferred shipping</span
							>
						</div>
					</div>
					<div v-if="workspace.can_manage" class="flex gap-2 shrink-0">
						<button type="button" class="btn-secondary" @click="beginEdit(address)">
							Edit
						</button>
						<button
							type="button"
							class="btn-secondary text-bad"
							:disabled="saving"
							@click="remove(address)"
						>
							Delete
						</button>
					</div>
				</div>
			</article>
		</section>
	</div>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { RouterLink } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import { call } from "../lib/frappe";

const METHOD = "volunteering.volunteering.office_addresses";
const loading = ref(true);
const saving = ref(false);
const editing = ref(false);
const error = ref("");
const workspace = reactive({ company: "", can_manage: false, addresses: [], address_types: [] });
const blank = () => ({
	name: "",
	modified: "",
	address_title: "",
	address_type: "Office",
	address_line1: "",
	address_line2: "",
	city: "",
	county: "",
	state: "",
	country: "India",
	pincode: "",
	email_id: "",
	phone: "",
	is_primary_address: false,
	is_shipping_address: false,
	disabled: false,
});
const form = reactive(blank());

function apply(data) {
	Object.assign(workspace, data || {});
}
function resetForm(values = {}) {
	Object.assign(form, blank(), values, {
		is_primary_address: Boolean(values.is_primary_address),
		is_shipping_address: Boolean(values.is_shipping_address),
		disabled: Boolean(values.disabled),
	});
}
function beginAdd() {
	resetForm();
	editing.value = true;
	error.value = "";
}
function beginEdit(address) {
	resetForm(address);
	editing.value = true;
	error.value = "";
	window.scrollTo({ top: 0, behavior: "smooth" });
}
function cancelEdit() {
	editing.value = false;
	resetForm();
}
function locality(address) {
	return [address.city, address.county, address.state].filter(Boolean).join(", ");
}

async function load() {
	loading.value = true;
	error.value = "";
	try {
		apply(await call(`${METHOD}.get_office_address_workspace`));
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		loading.value = false;
	}
}
async function save() {
	saving.value = true;
	error.value = "";
	try {
		apply(
			await call(`${METHOD}.save_office_address`, {
				details: { ...form },
				name: form.name || null,
				expected_modified: form.modified || null,
			}),
		);
		cancelEdit();
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
async function remove(address) {
	if (!window.confirm(`Delete ${address.address_title}?`)) return;
	saving.value = true;
	error.value = "";
	try {
		apply(
			await call(`${METHOD}.delete_office_address`, {
				name: address.name,
				expected_modified: address.modified,
			}),
		);
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-4 sm:p-5 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-grid {
	@apply grid sm:grid-cols-2 gap-3;
}
.field-label {
	@apply block text-sm font-medium text-ink;
}
.field-input {
	@apply mt-1 w-full rounded-xl border border-line bg-bg px-3 py-2 text-ink font-normal;
}
.field-input:focus {
	@apply outline-none ring-2 ring-accent border-accent;
}
.badge {
	@apply inline-flex rounded-full bg-soft px-2.5 py-1 text-xs text-muted;
}
button:disabled {
	@apply opacity-60 cursor-not-allowed;
}
</style>
