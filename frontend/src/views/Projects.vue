<template>
	<div class="space-y-6 project-workspace">
		<PageHeader
			title="Projects"
			subtitle="Give spending a purpose. Keep delivery, evidence and financial authority separate."
			eyebrow="Workspace"
		>
			<template #actions>
				<RouterLink to="/home" class="btn-secondary">Home</RouterLink>
				<button v-if="caps.can_create && !editing" class="btn-primary" @click="create">
					Propose a project
				</button>
				<button v-if="editing" class="btn-secondary" @click="back">
					Projects and proposals
				</button>
				<button
					v-if="saved && !requestMode && caps.can_propose_changes"
					class="btn-primary"
					@click="proposeChange"
				>
					Propose changes
				</button>
				<button
					v-if="editing && requestMode && detailEditable"
					class="btn-primary"
					:disabled="busy"
					@click="projectForm?.requestSubmit()"
				>
					{{ saving ? "Saving…" : "Save draft / edits" }}
				</button>
			</template>
		</PageHeader>

		<p v-if="loading" class="text-muted" role="status">Loading projects…</p>
		<div
			v-if="error"
			class="rounded-xl border border-bad bg-bad-soft p-4 text-sm text-bad"
			role="alert"
		>
			{{ error }}
		</div>
		<div
			v-if="notice"
			class="rounded-xl border border-ok bg-ok-soft p-4 text-sm text-ink"
			role="status"
		>
			{{ notice }}
		</div>

		<template v-if="!loading && !editing">
			<section class="form-card" aria-labelledby="requests-title">
				<h2 id="requests-title" class="form-title">
					{{
						caps.can_manage
							? "Project approval queue and history"
							: "Your proposals and change requests"
					}}
				</h2>
				<p class="form-hint">
					One Projects Manager's approval activates a new project or applies later
					changes. Pending requests do not change the approved project.
				</p>
				<label class="field-label"
					>Request status<select v-model="requestFilter" class="field-input">
						<option value="">All requests</option>
						<option>Pending Approval</option>
						<option>Draft</option>
						<option>Correction Required</option>
						<option>Approved</option>
						<option>Rejected</option>
						<option>Withdrawn</option>
					</select></label
				>
				<p v-if="!filteredRequests.length" class="text-sm text-muted mt-4">
					No matching requests.
				</p>
				<button
					v-for="item in filteredRequests"
					:key="item.name"
					class="project-tile block w-full text-left mt-3"
					@click="openRequest(item.name)"
				>
					<span class="project-badge">{{ item.proposal_status }}</span
					><strong class="block mt-2">{{ item.title }}</strong
					><span class="text-xs text-muted"
						>{{ item.request_kind }} · {{ item.proposed_by }}</span
					>
				</button>
			</section>
			<div class="flex flex-wrap items-center gap-3">
				<label class="grow field-label"
					>Find a project<input
						v-model="search"
						class="field-input"
						placeholder="Search by name, project ID or status"
				/></label>
				<div class="text-sm text-muted pt-5">{{ filteredProjects.length }} projects</div>
			</div>
			<p class="text-sm text-muted">
				These are approved projects. Open a card to view the effective details.
			</p>
			<label v-if="caps.can_manage" class="text-sm"
				><input v-model="includeRemoved" type="checkbox" @change="load" /> Include removed
				projects</label
			>
			<div v-if="!filteredProjects.length" class="form-card text-center py-10">
				<h2 class="form-title">No projects here yet</h2>
				<p class="text-sm text-muted">
					{{
						caps.can_create
							? "Create a project to define its purpose, people and permitted expense accounts."
							: "Only your own projects and projects you are a member of appear here, unless another role grants wider access."
					}}
				</p>
			</div>
			<div class="grid sm:grid-cols-2 gap-4">
				<button
					v-for="project in filteredProjects"
					:key="project.name"
					class="project-tile text-left"
					@click="open(project.name)"
				>
					<div class="flex justify-between gap-3 items-start">
						<span class="text-xs font-medium text-muted">{{ project.name }}</span
						><span class="project-badge">{{
							project.operational_status || project.status
						}}</span>
					</div>
					<h2 class="text-lg font-semibold mt-4 text-ink">{{ project.project_name }}</h2>
					<p class="text-sm text-accent mt-2">Open project →</p>
					<div
						class="mt-5 pt-3 border-t border-line text-xs text-muted flex flex-wrap gap-2 justify-between"
					>
						<span>{{
							project.project_owner || "Legacy setup · owner not assigned"
						}}</span>
					</div>
				</button>
			</div>
		</template>

		<form
			v-if="!loading && editing"
			ref="projectForm"
			class="space-y-5"
			@submit.prevent="save"
		>
			<div v-if="requestMode" class="form-card">
				<h2 class="form-title">
					{{ request?.request_kind || (saved ? "Project Change" : "New Project") }} ·
					{{ request?.proposal_status || "Unsaved draft" }}
				</h2>
				<p class="form-hint">
					This is a proposal, not the effective project. Save it, then submit for
					approval. Submitted requests are locked for the proposer until returned for
					correction.
				</p>
				<p v-if="request?.stale" class="text-bad text-sm mb-3" role="alert">
					The approved project has changed. A manager must review the current baseline
					before approval.
				</p>
				<label class="field-label"
					>Reason for this proposal / change<textarea
						v-model.trim="reason"
						class="field-input"
						rows="2"
						:disabled="!detailEditable"
						:required="Boolean(saved)"
					/>
				</label>
				<div v-if="request?.can_review" class="mt-4 space-y-3">
					<details>
						<summary class="cursor-pointer font-semibold">
							Compare approved details with requested changes
						</summary>
						<div class="form-grid mt-3">
							<pre class="revision-values">
Approved: {{ JSON.stringify(request.current, null, 2) }}</pre>
							<pre class="revision-values">
Requested patch: {{ JSON.stringify(request.data, null, 2) }}</pre>
						</div>
					</details>
					<label class="field-label"
						>Review comments<textarea
							v-model.trim="comments"
							class="field-input"
							rows="2"
							placeholder="Required for return, rejection or refreshing a stale baseline"
						/>
					</label>
					<div class="flex flex-wrap gap-2">
						<button
							type="button"
							class="btn-primary"
							:disabled="busy || request.stale"
							@click="decide('approve')"
						>
							{{ changed ? "Approve with my edits" : "Approve proposal" }}</button
						><button
							type="button"
							class="btn-secondary"
							:disabled="busy"
							@click="decide('return')"
						>
							Return for correction</button
						><button
							type="button"
							class="btn-secondary text-bad"
							:disabled="busy"
							@click="decide('reject')"
						>
							Reject proposal</button
						><button
							v-if="request.stale"
							type="button"
							class="btn-secondary"
							:disabled="busy"
							@click="decide('rebase')"
						>
							Refresh approved baseline
						</button>
					</div>
				</div>
				<div v-else-if="request?.can_edit" class="flex flex-wrap gap-2 mt-4">
					<button
						type="button"
						class="btn-primary"
						:disabled="busy"
						@click="submitRequest"
					>
						Submit for project approval</button
					><button
						type="button"
						class="btn-secondary"
						:disabled="busy"
						@click="withdraw"
					>
						Withdraw draft
					</button>
				</div>
				<RouterLink
					v-if="request?.proposal_status === 'Approved'"
					:to="{ path: '/projects', query: { project: request.project } }"
					class="text-accent underline inline-block mt-4"
					>Open approved project</RouterLink
				>
			</div>
			<p v-else class="text-sm text-muted">
				Approved details are read-only. Use Propose changes to request an update.
			</p>
			<div
				v-if="saved?.legacy"
				class="rounded-xl border border-warn bg-warn-soft p-4 text-sm text-ink"
			>
				<strong>Existing project — complete the new setup</strong>
				<p class="mt-1">
					Its old records are preserved. Choose the actual owner and participants before
					saving to adopt the new project structure.
				</p>
			</div>
			<div v-if="saved" class="form-card grid sm:grid-cols-3 gap-4">
				<div>
					<span class="text-xs text-muted">Operational status</span>
					<p class="font-semibold mt-1">{{ saved.operational_status }}</p>
				</div>
				<div v-if="showFinance">
					<span class="text-xs text-muted">Committed project spending</span>
					<p class="font-semibold mt-1">{{ currency(saved.committed) }}</p>
				</div>
				<div v-if="showFinance">
					<span class="text-xs text-muted">Financial closure</span>
					<p class="font-semibold mt-1">
						{{
							saved.financial_closed
								? "Closed"
								: "Open · may still have payments to settle"
						}}
					</p>
				</div>
			</div>

			<section class="form-card" aria-labelledby="identity-title">
				<div class="section-eyebrow">01 · Identity and lifecycle</div>
				<h2 id="identity-title" class="form-title">What are we doing?</h2>
				<fieldset :disabled="!detailEditable" class="form-grid">
					<label class="field-label"
						>Project name *<input
							v-model.trim="form.project_name"
							required
							maxlength="140"
							class="field-input"
					/></label>
					<label class="field-label sm:col-span-2"
						>Purpose / scope *<textarea
							v-model.trim="form.project_purpose"
							required
							rows="3"
							maxlength="4000"
							class="field-input"
							placeholder="Why this project exists and what spending belongs to it"
						></textarea>
					</label>
					<label class="field-label"
						>Operational status *<select
							v-model="form.operational_status"
							class="field-input"
						>
							<option v-for="state in states" :key="state">
								{{ state }}
							</option></select
						><span class="field-help"
							>Only Active projects accept new claims. Completion does not settle
							outstanding payments.</span
						></label
					>
					<label class="field-label"
						>Expected start date<input
							v-model="form.expected_start_date"
							type="date"
							class="field-input"
					/></label>
					<label class="field-label"
						>Expected end date<input
							v-model="form.expected_end_date"
							type="date"
							:min="form.expected_start_date || undefined"
							class="field-input"
					/></label>
				</fieldset>
			</section>

			<section class="form-card" aria-labelledby="people-title">
				<div class="section-eyebrow">02 · People and delivery</div>
				<h2 id="people-title" class="form-title">Who owns it? Who takes part?</h2>
				<p class="form-hint">
					Membership allows work and claims against this project. It does not grant
					expense approval or Accounts User rights.
				</p>
				<label class="field-label"
					>Project owner *<select
						v-model="form.project_owner"
						required
						class="field-input"
						:disabled="!detailEditable"
					>
						<option value="">Choose one owner</option>
						<option v-for="user in peopleOptions" :key="user.name" :value="user.name">
							{{ user.full_name }} · {{ user.name }}
						</option>
					</select></label
				>
				<div class="mt-4">
					<div class="flex justify-between gap-3 text-sm mb-2">
						<span class="font-semibold">Selected participants *</span
						><span class="text-muted">{{ form.participants.length }} selected</span>
					</div>
					<input
						v-if="detailEditable"
						v-model="peopleSearch"
						aria-label="Find participants"
						class="field-input mb-2"
						placeholder="Find a colleague by name or email"
					/>
					<div
						class="rounded-xl border border-line divide-y divide-line max-h-60 overflow-y-auto"
					>
						<label
							v-for="user in filteredPeople"
							:key="user.name"
							class="flex items-center gap-3 px-3 py-2.5 cursor-pointer text-sm"
						>
							<input
								v-model="form.participants"
								type="checkbox"
								:value="user.name"
								:disabled="!detailEditable"
								:aria-label="`Add participant ${user.name}`"
							/>
							<span
								><strong class="block font-medium">{{ user.full_name }}</strong
								><span class="text-xs text-muted">{{ user.name }}</span></span
							>
						</label>
					</div>
				</div>
				<div class="space-y-2 mt-4">
					<label v-for="user in form.participants" :key="user" class="field-label"
						>{{ user }} · Visibility<select
							v-model="form.memberLevels[user]"
							:disabled="!detailEditable"
							class="field-input"
						>
							<option>Basic</option>
							<option>Financial</option>
						</select></label
					>
					<p class="field-help">
						Every listed member can submit bills. Financial visibility does not grant
						project approval or payment authority.
					</p>
				</div>
				<label class="field-label mt-4"
					>Expected outcomes / deliverables<textarea
						v-model.trim="form.project_outcomes"
						rows="3"
						maxlength="4000"
						class="field-input"
						:disabled="!detailEditable"
						placeholder="What should be delivered? How will we know it is complete?"
					></textarea>
				</label>
			</section>

			<section v-if="showFinance" class="form-card" aria-labelledby="budget-title">
				<div class="section-eyebrow">03 · Budget and permitted accounts</div>
				<h2 id="budget-title" class="form-title">Where can spending go?</h2>
				<p class="form-hint">
					Project and expense-account controls are independent. These allocations are
					budgets—not bank balances. Employee claims show only the accounts permitted
					here.
				</p>
				<p
					v-if="saved && !budgetEditable"
					class="rounded-xl bg-soft text-sm px-3 py-2 mb-4"
				>
					Financial changes require an approved project change request.
				</p>
				<fieldset :disabled="!budgetEditable" class="form-grid">
					<label class="field-label sm:col-span-2"
						>Default cost centre *<select
							v-model="form.cost_center"
							required
							class="field-input"
						>
							<option value="">Choose a cost centre</option>
							<option
								v-for="centre in companyCentres"
								:key="centre.name"
								:value="centre.name"
							>
								{{ centre.name }}
							</option></select
						><span class="field-help"
							>Choose a leaf from the Chart of Cost Centres. Several projects can
							share one.</span
						></label
					>
					<label class="field-label"
						>Overall project budget control *<select
							v-model="form.project_budget_control"
							class="field-input"
						>
							<option v-for="mode in modes" :key="mode">{{ mode }}</option>
						</select></label
					>
					<label class="field-label"
						>Total approved budget ({{ companyCurrency }})<input
							v-model.number="form.total_approved_budget"
							type="number"
							min="0"
							step="0.01"
							:required="form.project_budget_control !== 'No Control'"
							class="field-input"
					/></label>
					<label class="field-label sm:col-span-2"
						>Expense-account budget control *<select
							v-model="form.account_budget_control"
							class="field-input"
						>
							<option v-for="mode in modes" :key="mode">{{ mode }}</option>
						</select></label
					>
				</fieldset>
				<div class="grid sm:grid-cols-3 gap-2 my-4">
					<div
						v-for="mode in modeHints"
						:key="mode.title"
						class="rounded-xl bg-bg border border-line p-3 text-xs"
					>
						<strong>{{ mode.title }}</strong>
						<p class="text-muted mt-1 leading-relaxed">{{ mode.hint }}</p>
					</div>
				</div>
				<div class="flex justify-between gap-3 items-center mb-3">
					<h3 class="text-sm font-semibold">Permitted expense accounts *</h3>
					<button
						v-if="budgetEditable"
						type="button"
						class="btn-secondary text-sm"
						:disabled="form.account_budgets.length >= 100"
						@click="addAccount"
					>
						Add account
					</button>
				</div>
				<div class="space-y-3">
					<fieldset
						v-for="(row, index) in form.account_budgets"
						:key="row.key"
						:disabled="!budgetEditable"
						class="rounded-xl border border-line bg-bg p-3"
					>
						<div class="flex justify-between items-center mb-3">
							<strong class="text-xs text-muted">Account {{ index + 1 }}</strong
							><button
								v-if="budgetEditable"
								type="button"
								class="text-xs text-bad"
								@click="form.account_budgets.splice(index, 1)"
							>
								Remove
							</button>
						</div>
						<div class="form-grid">
							<SearchSelect
								v-model="row.expense_account"
								label="Expense account *"
								required
								:disabled="!budgetEditable"
								:options="
									availableAccounts(row).map((account) => ({
										value: account.name,
										label: account.account_name,
										description: account.name,
									}))
								"
								@change="accountChanged(row)"
							/>
							<label class="field-label"
								>Employee-facing label<input
									v-model.trim="row.employee_label"
									maxlength="140"
									class="field-input"
									placeholder="Plain-language name shown to employees"
							/></label>
							<label v-if="row.approved_amount !== undefined" class="field-label"
								>Account allocation ({{ companyCurrency }})<input
									v-model.number="row.approved_amount"
									type="number"
									min="0"
									step="0.01"
									:required="form.account_budget_control !== 'No Control'"
									class="field-input"
								/><span class="field-help"
									>Optional when account control is No Control.</span
								></label
							>
							<label class="flex items-center gap-2 text-sm sm:pt-6"
								><input v-model="row.is_active" type="checkbox" /> Available for
								employee claims</label
							>
						</div>
					</fieldset>
				</div>
				<p
					v-if="budgetEditable && form.account_budget_control !== 'No Control'"
					class="field-help mt-3"
				>
					Allocated across accounts: {{ currency(allocatedTotal) }}. Each account ceiling
					is enforced independently of the total project ceiling.
				</p>
				<label v-if="false" class="field-label mt-4"
					>Reason for financial setup changes<textarea
						v-model.trim="form.revision_reason"
						rows="2"
						maxlength="2000"
						class="field-input"
						placeholder="Explain any changes to limits, allowed accounts, cost centre or financial closure"
					></textarea>
				</label>
			</section>
			<section v-if="!showFinance" class="form-card">
				<h2 class="form-title">Accounts available for your bills</h2>
				<p class="form-hint">
					Only permitted account names are shown, not budgets or ledger balances.
				</p>
				<p
					v-for="row in saved?.permitted_accounts || []"
					:key="row.expense_account"
					class="text-sm mt-2"
				>
					{{ row.employee_label || row.expense_account }}
				</p>
			</section>

			<section class="form-card">
				<h2 class="form-title">Supporting records</h2>
				<p class="form-hint">
					Project plans, approved budgets and other supporting documents. Expense
					receipts still belong on the individual claim.
				</p>
				<ul v-if="attachments.length" class="space-y-2 text-sm mb-4">
					<li v-for="file in attachments" :key="file.name">
						<a
							:href="file.file_url"
							target="_blank"
							rel="noopener"
							class="text-accent underline"
							>{{ file.file_name }}</a
						><span class="text-xs text-muted ml-2">Private</span>
					</li>
				</ul>
				<label v-if="request && detailEditable" class="field-label"
					>Document visibility<select v-model="documentVisibility" class="field-input">
						<option>Basic</option>
						<option>Financial</option>
					</select></label
				>
				<label v-if="request && detailEditable" class="field-label"
					>Add a supporting document<input
						type="file"
						class="field-input"
						:disabled="uploading"
						@change="upload"
					/><span class="field-help"
						>Private evidence on this request; published to the project only after
						approval, up to 10 MB.</span
					></label
				>
				<p v-if="requestMode && !request" class="text-sm text-muted">
					Save the draft first, then attach its supporting documents here.
				</p>
			</section>

			<section class="rounded-2xl border border-line bg-accent-soft p-5">
				<h2 class="form-title">Financial responsibilities stay company-wide</h2>
				<div class="grid sm:grid-cols-3 gap-4 text-sm">
					<div>
						<strong>Receipt reviewer</strong>
						<p class="text-muted mt-1">Verifies evidence or requests corrections.</p>
					</div>
					<div>
						<strong>Assigned expense approver</strong>
						<p class="text-muted mt-1">
							Uses the employee hierarchy and grade limits. Project ownership is not
							approval authority.
						</p>
					</div>
					<div>
						<strong>Accounts team</strong>
						<p class="text-muted mt-1">
							Settles approved, verified claims from a cash/bank ledger and clears
							the employee payable.
						</p>
					</div>
				</div>
			</section>

			<details class="form-card">
				<summary class="cursor-pointer font-semibold">
					Optional project organisation
				</summary>
				<fieldset :disabled="!detailEditable" class="form-grid mt-4">
					<label class="field-label"
						>Project type<select v-model="form.project_type" class="field-input">
							<option value="">No type</option>
							<option v-for="type in options.project_types" :key="type">
								{{ type }}
							</option>
						</select></label
					><label class="field-label"
						>Priority<select v-model="form.priority" class="field-input">
							<option>Low</option>
							<option>Medium</option>
							<option>High</option>
						</select></label
					>
				</fieldset>
				<p v-if="saved" class="field-help mt-4">
					Milestones, tasks and progress tracking remain available in
					<a
						:href="`/desk/project/${encodeURIComponent(saved.name)}`"
						class="text-accent underline"
						>the detailed Desk view</a
					>.
				</p>
			</details>

			<section v-if="saved && showFinance" class="form-card">
				<h2 class="form-title">Financial closure</h2>
				<label class="flex gap-3 items-start text-sm"
					><input
						v-model="form.financial_closed"
						type="checkbox"
						class="mt-1"
						:disabled="!budgetEditable"
					/><span
						>Financially close this project<span class="block text-muted mt-1"
							>Close only after pending claims, purchase orders and outstanding
							invoices are settled or closed. A recorded reason is required; this is
							separate from operational completion.</span
						></span
					></label
				>
			</section>

			<details v-if="saved?.revisions.length" class="form-card">
				<summary class="cursor-pointer font-semibold">
					Budget and account revision history · {{ saved.revisions.length }}
				</summary>
				<div class="space-y-4 mt-4">
					<article
						v-for="revision in saved.revisions"
						:key="revision.changed_on"
						class="border-t border-line pt-4 text-sm"
					>
						<p class="font-semibold">{{ revision.reason }}</p>
						<p class="text-xs text-muted mt-1">
							{{ revision.changed_by }} · {{ revision.changed_on }}
						</p>
						<div class="grid sm:grid-cols-2 gap-3 mt-3">
							<div class="rounded-xl bg-bg p-3">
								<span class="text-xs font-semibold text-muted">Before</span>
								<pre class="revision-values">{{
									revisionText(revision.before_values)
								}}</pre>
							</div>
							<div class="rounded-xl bg-bg p-3">
								<span class="text-xs font-semibold text-muted">After</span>
								<pre class="revision-values">{{
									revisionText(revision.after_values)
								}}</pre>
							</div>
						</div>
					</article>
				</div>
			</details>
			<details v-if="request?.events.length" class="form-card" open>
				<summary class="cursor-pointer font-semibold">Proposal review history</summary>
				<article
					v-for="(event, index) in request.events"
					:key="index"
					class="border-t border-line pt-3 mt-3 text-sm"
				>
					<strong>{{ event.action }}</strong>
					<p class="text-xs text-muted">{{ event.actor }} · {{ event.acted_on }}</p>
					<p class="mt-2 whitespace-pre-wrap">{{ event.comment }}</p>
					<details v-if="Object.keys(event.after).length">
						<summary class="cursor-pointer text-xs mt-2">Recorded details</summary>
						<div class="form-grid">
							<pre class="revision-values">{{
								JSON.stringify(event.before, null, 2)
							}}</pre>
							<pre class="revision-values">{{
								JSON.stringify(event.after, null, 2)
							}}</pre>
						</div>
					</details>
				</article>
			</details>
			<section v-if="saved && !requestMode && caps.can_manage" class="form-card">
				<h2 class="form-title">Remove an unused project</h2>
				<p class="form-hint">
					Only projects without financial records can be removed. The approval history is
					retained and removal is recoverable.
				</p>
				<label class="field-label"
					>Removal reason<input v-model.trim="comments" class="field-input" /></label
				><button
					type="button"
					class="btn-secondary text-bad mt-3"
					:disabled="busy"
					@click="removeProject"
				>
					Remove unused project
				</button>
			</section>

			<div v-if="detailEditable || budgetEditable" class="project-save-bar">
				<p class="text-xs text-muted">
					{{
						saved
							? "Pending changes leave the approved project unchanged."
							: "Saves a proposal—not an active project or payment."
					}}
				</p>
				<button class="btn-primary px-5 py-2.5 shrink-0" type="submit" :disabled="busy">
					{{ saving ? "Saving…" : "Save draft / edits" }}
				</button>
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { RouterLink, useRoute, useRouter } from "vue-router";
import PageHeader from "../components/PageHeader.vue";
import SearchSelect from "../components/SearchSelect.vue";
import { call } from "../lib/frappe";
import { loadHomePayload } from "../lib/home";

const method = "volunteering.volunteering.project_workspace.";
const proposalMethod = "volunteering.volunteering.project_proposals.";
const request = ref(null),
	requests = ref([]),
	requestFilter = ref(""),
	requestMode = ref(false),
	includeRemoved = ref(false);
const reason = ref(""),
	comments = ref(""),
	documentVisibility = ref("Basic");
const baseline = ref({});
const route = useRoute(),
	router = useRouter();
const loading = ref(true),
	editing = ref(false),
	saving = ref(false),
	uploading = ref(false);
const error = ref(""),
	notice = ref(""),
	search = ref(""),
	peopleSearch = ref("");
const projects = ref([]),
	saved = ref(null),
	caps = ref({});
const options = ref({
	users: [],
	companies: [],
	cost_centres: [],
	expense_accounts: [],
	project_types: [],
});
const modes = ["No Control", "Warn Only", "Strict"],
	states = ["Planned", "Active", "On Hold", "Completed", "Cancelled"];
const modeHints = [
	{ title: "No Control", hint: "Track spending without enforcing amount limits." },
	{ title: "Warn Only", hint: "Show an overrun warning; allow approval to continue." },
	{
		title: "Strict",
		hint: "Block approval until revised or explicitly overridden by authorised financial authority.",
	},
];
const form = reactive({});
const projectForm = ref(null);
let rowKey = 0;
const detailEditable = computed(
	() => requestMode.value && (!request.value || request.value.can_edit),
);
const showFinance = computed(() =>
	requestMode.value
		? !request.value
			? !saved.value || caps.value.can_view_financials
			: request.value.can_view_financials
		: caps.value.can_view_financials,
);
const budgetEditable = computed(() => detailEditable.value && showFinance.value);
const busy = computed(() => saving.value || uploading.value);
const attachments = computed(() => [
	...(saved.value?.attachments || []),
	...(request.value?.attachments || []),
]);
const filteredRequests = computed(() =>
	requests.value.filter(
		(item) => !requestFilter.value || item.proposal_status === requestFilter.value,
	),
);
const changed = computed(
	() => request.value && JSON.stringify(patchData()) !== JSON.stringify(request.value.data),
);
const filteredProjects = computed(() =>
	projects.value.filter((project) =>
		`${project.project_name} ${project.name} ${project.operational_status || project.status}`
			.toLowerCase()
			.includes(search.value.toLowerCase()),
	),
);
const peopleOptions = computed(() =>
	options.value.users.length
		? options.value.users
		: [...new Set([form.project_owner, ...(form.participants || [])])]
				.filter(Boolean)
				.map((name) => ({ name, full_name: name })),
);
const filteredPeople = computed(() =>
	peopleOptions.value.filter((user) =>
		detailEditable.value
			? `${user.name} ${user.full_name}`
					.toLowerCase()
					.includes(peopleSearch.value.toLowerCase())
			: form.participants.includes(user.name),
	),
);
const companyCentres = computed(() =>
	options.value.cost_centres
		.filter((row) => row.company === form.company)
		.concat(
			form.cost_center &&
				!options.value.cost_centres.some((row) => row.name === form.cost_center)
				? [{ name: form.cost_center }]
				: [],
		),
);
const companyCurrency = computed(
	() =>
		options.value.companies.find((row) => row.name === form.company)?.default_currency ||
		"INR",
);
const allocatedTotal = computed(() =>
	(form.account_budgets || []).reduce((sum, row) => sum + Number(row.approved_amount || 0), 0),
);
const currency = (value) =>
	new Intl.NumberFormat("en-IN", { style: "currency", currency: companyCurrency.value }).format(
		Number(value || 0),
	);

function populate(data = {}) {
	Object.keys(form).forEach((key) => delete form[key]);
	Object.assign(
		form,
		{
			project_name: "",
			company: options.value.default_company || "",
			project_purpose: "",
			project_owner: options.value.current_user || "",
			operational_status: "Planned",
			expected_start_date: "",
			expected_end_date: "",
			project_outcomes: "",
			cost_center: "",
			total_approved_budget: 0,
			project_budget_control: "No Control",
			account_budget_control: "No Control",
			project_type: "",
			priority: "Medium",
			participants: options.value.current_user ? [options.value.current_user] : [],
			account_budgets: [],
			financial_closed: false,
			revision_reason: "",
		},
		data,
	);
	if (!form.company) form.company = options.value.default_company || "";
	form.participants = [...(form.participants || [])];
	form.memberLevels = Object.fromEntries(
		(data.members || []).map((row) => [row.user, row.access_level || "Basic"]),
	);
	if (form.participants.some((row) => typeof row === "object")) {
		form.memberLevels = Object.fromEntries(
			form.participants.map((row) => [row.user, row.access_level || "Basic"]),
		);
		form.participants = form.participants.map((row) => row.user);
	}
	form.participants.forEach((user) => {
		if (!form.memberLevels[user]) form.memberLevels[user] = "Basic";
	});
	form.account_budgets = (form.account_budgets || []).map((row) => ({
		...row,
		is_active: Boolean(row.is_active),
		key: ++rowKey,
	}));
	if (!saved.value && !form.account_budgets.length) addAccount();
}

async function load() {
	loading.value = true;
	error.value = "";
	notice.value = "";
	peopleSearch.value = "";
	request.value = null;
	requestMode.value = false;
	reason.value = comments.value = "";
	try {
		if (route.query.proposal) {
			request.value = await call(proposalMethod + "get_proposal", {
				proposal: route.query.proposal,
			});
			requestMode.value = true;
			saved.value =
				request.value.request_kind === "Project Change"
					? await call(method + "get_project", { project: request.value.project })
					: null;
			caps.value =
				saved.value?.capabilities || (await call(method + "get_projects")).capabilities;
			options.value = request.value.can_edit
				? await call(method + "get_setup_options", { project: saved.value?.name })
				: {
						users: [],
						companies: [],
						cost_centres: [],
						expense_accounts: [],
						project_types: [],
					};
			baseline.value = saved.value ? valueData(saved.value) : {};
			populate({ ...baseline.value, ...request.value.data });
			reason.value = request.value.request_reason;
			editing.value = true;
		} else if (route.query.project) {
			saved.value = await call(method + "get_project", { project: route.query.project });
			caps.value = saved.value.capabilities;
			options.value = caps.value.can_propose_changes
				? await call(method + "get_setup_options", { project: saved.value.name })
				: {
						users: [],
						companies: [{ name: saved.value.company }],
						cost_centres: [],
						expense_accounts: [],
						project_types: saved.value.project_type ? [saved.value.project_type] : [],
					};
			populate(saved.value);
			baseline.value = valueData(saved.value);
			editing.value = true;
		} else {
			const result = await call(method + "get_projects", {
				include_removed: Number(includeRemoved.value),
			});
			requests.value = await call(proposalMethod + "get_proposals");
			if (route.query.queue) requestFilter.value = "Pending Approval";
			projects.value = result.projects;
			caps.value = result.capabilities;
			saved.value = null;
			editing.value = Boolean(route.query.new);
			requestMode.value = editing.value;
			if (editing.value) {
				if (!caps.value.can_create) throw new Error("Your role cannot create projects.");
				options.value = await call(method + "get_setup_options");
				populate();
				baseline.value = {};
			}
		}
	} catch (e) {
		error.value = e.message || String(e);
		editing.value = false;
	} finally {
		loading.value = false;
	}
}

function availableAccounts(row) {
	const accounts = options.value.expense_accounts.filter(
		(account) => account.company === form.company,
	);
	if (row.expense_account && !accounts.some((account) => account.name === row.expense_account))
		accounts.push({
			name: row.expense_account,
			account_name: row.employee_label || row.expense_account,
		});
	return accounts;
}
function addAccount() {
	form.account_budgets.push({
		key: ++rowKey,
		expense_account: "",
		employee_label: "",
		approved_amount: 0,
		is_active: true,
	});
}
function accountChanged(row) {
	row.employee_label =
		options.value.expense_accounts.find((account) => account.name === row.expense_account)
			?.account_name || "";
}
function create() {
	router.push({ path: "/projects", query: { new: "1" } });
}
function open(project) {
	router.push({ path: "/projects", query: { project } });
}
function openRequest(proposal) {
	router.push({ path: "/projects", query: { proposal } });
}
function proposeChange() {
	requestMode.value = true;
	request.value = null;
	baseline.value = valueData(saved.value);
	populate(saved.value);
}
function back() {
	router.push("/projects");
}

async function save() {
	if (uploading.value) {
		error.value = "Wait for the supporting document upload to finish.";
		return;
	}
	error.value = "";
	notice.value = "";
	saving.value = true;
	try {
		const result = await call(proposalMethod + "save_proposal", {
			project: request.value ? undefined : saved.value?.name,
			proposal: request.value?.name,
			modified: request.value?.modified,
			data: patchData(),
			reason: reason.value,
		});
		request.value = result;
		if (route.query.proposal !== result.name)
			await router.replace({ path: "/projects", query: { proposal: result.name } });
		notice.value = `Request saved. The approved project has not changed.`;
		return result;
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}

const detailKeys = [
	"project_name",
	"project_purpose",
	"project_outcomes",
	"project_owner",
	"operational_status",
	"expected_start_date",
	"expected_end_date",
	"project_type",
	"priority",
];
const financeKeys = [
	"cost_center",
	"total_approved_budget",
	"project_budget_control",
	"account_budget_control",
	"financial_closed",
];
function valueData(value) {
	const data = Object.fromEntries(
		[...detailKeys, ...financeKeys]
			.filter((key) => key in value)
			.map((key) => [key, value[key]]),
	);
	data.participants = (value.members || value.participants || []).map((row) =>
		typeof row === "string"
			? { user: row, access_level: "Basic" }
			: { user: row.user, access_level: row.access_level || "Basic" },
	);
	if (value.account_budgets)
		data.account_budgets = value.account_budgets.map((row) => ({
			expense_account: row.expense_account,
			employee_label: row.employee_label || "",
			approved_amount: Number(row.approved_amount || 0),
			is_active: Number(row.is_active),
		}));
	return data;
}
function patchData() {
	const data = Object.fromEntries(detailKeys.map((key) => [key, form[key] || ""]));
	data.participants = form.participants.map((user) => ({
		user,
		access_level: form.memberLevels[user] || "Basic",
	}));
	if (showFinance.value) {
		financeKeys.forEach((key) => {
			data[key] = key === "financial_closed" ? Boolean(form[key]) : form[key];
		});
		data.account_budgets = form.account_budgets.map((row) => ({
			expense_account: row.expense_account,
			employee_label: row.employee_label || "",
			approved_amount: Number(row.approved_amount || 0),
			is_active: Number(row.is_active),
		}));
	}
	if (request.value?.data.is_archived !== undefined)
		data.is_archived = request.value.data.is_archived;
	return saved.value
		? Object.fromEntries(
				Object.entries(data).filter(
					([key, value]) =>
						JSON.stringify(value) !== JSON.stringify(baseline.value[key]),
				),
			)
		: data;
}
async function submitRequest() {
	const result = await save();
	if (!result) return;
	saving.value = true;
	try {
		request.value = await call(proposalMethod + "submit_proposal", {
			proposal: result.name,
			modified: result.modified,
		});
		notice.value = "Submitted for project approval. The effective project is unchanged.";
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
async function decide(action) {
	error.value = "";
	if (action !== "approve" && !comments.value) {
		error.value = "Enter review comments first.";
		return;
	}
	saving.value = true;
	try {
		request.value = await call(proposalMethod + "review_proposal", {
			proposal: request.value.name,
			modified: request.value.modified,
			action,
			comments: comments.value,
			data: patchData(),
		});
		await loadHomePayload();
		await load();
		notice.value =
			action === "approve"
				? "Approved. This one manager decision applies the project configuration."
				: "Review decision recorded.";
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
async function withdraw() {
	saving.value = true;
	try {
		request.value = await call(proposalMethod + "withdraw_proposal", {
			proposal: request.value.name,
			modified: request.value.modified,
		});
		notice.value = "Draft withdrawn. Its history is retained.";
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}
async function removeProject() {
	if (!comments.value) {
		error.value = "Enter a removal reason.";
		return;
	}
	if (
		!window.confirm(
			"Remove this unused project from active listings? Its history will be retained.",
		)
	)
		return;
	saving.value = true;
	try {
		await call(proposalMethod + "remove_unused_project", {
			project: saved.value.name,
			modified: saved.value.modified,
			reason: comments.value,
		});
		await router.push("/projects");
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		saving.value = false;
	}
}

async function upload(event) {
	const file = event.target.files?.[0];
	if (!file) return;
	error.value = "";
	uploading.value = true;
	try {
		if (file.size > 10 * 1024 * 1024) throw new Error("Choose a document smaller than 10 MB.");
		const content = await new Promise((resolve, reject) => {
			const reader = new FileReader();
			reader.onerror = reject;
			reader.onload = () => resolve(String(reader.result).split(",")[1]);
			reader.readAsDataURL(file);
		});
		request.value = await call(proposalMethod + "upload_proposal_document", {
			proposal: request.value.name,
			modified: request.value.modified,
			visibility: documentVisibility.value,
			filename: file.name,
			content,
		});
		notice.value = "Supporting document attached privately.";
	} catch (e) {
		error.value = e.message || String(e);
	} finally {
		uploading.value = false;
		event.target.value = "";
	}
}

function revisionText(value) {
	const data = JSON.parse(value || "{}");
	if (!Object.keys(data).length) return "No previous setup";
	return [
		`Project: ${data.project_budget_control} · ${currency(data.total_approved_budget)}`,
		`Accounts: ${data.account_budget_control}`,
		`Cost centre: ${data.cost_center}`,
		...(data.account_budgets || []).map(
			(row) =>
				`${row.employee_label || row.expense_account}: ${currency(row.approved_amount)}${row.is_active ? "" : " (inactive)"}`,
		),
		`Financially ${data.financial_closed ? "closed" : "open"}`,
	].join("\n");
}
watch(() => route.fullPath, load);
onMounted(load);
</script>

<style scoped>
.form-card {
	@apply rounded-2xl border border-line bg-surface p-5 md:p-6 shadow-soft;
}
.form-title {
	@apply text-lg font-semibold text-ink mb-3;
}
.form-hint {
	@apply text-sm text-muted mb-4 leading-relaxed;
}
.form-grid {
	@apply grid sm:grid-cols-2 gap-4;
	min-width: 0;
	border: 0;
	padding: 0;
	margin: 0;
	background: transparent;
}
.field-label {
	@apply block text-sm font-medium text-ink;
	min-width: 0;
}
.field-input {
	@apply block w-full rounded-xl border border-line bg-surface px-3 py-2.5 mt-1 text-sm text-ink;
}
.field-input:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
.field-help {
	@apply block text-xs font-normal text-muted mt-1 leading-relaxed;
}
.section-eyebrow {
	@apply text-xs uppercase tracking-wider text-accent font-semibold mb-2;
}
.project-tile {
	@apply rounded-2xl border border-line bg-surface p-5 shadow-soft transition-all hover:shadow-lift hover:border-accent break-words;
}
.project-badge {
	@apply text-xs px-2.5 py-1 rounded-full bg-accent-soft text-accent font-medium shrink-0;
}
.project-save-bar {
	@apply flex items-center justify-between gap-3 rounded-2xl border border-line bg-surface p-4 shadow-lift;
}
.revision-values {
	@apply text-xs font-sans text-muted whitespace-pre-wrap break-words mt-2 leading-relaxed;
}
fieldset:disabled {
	opacity: 0.75;
}
button:disabled {
	@apply opacity-60 cursor-not-allowed;
}
</style>
