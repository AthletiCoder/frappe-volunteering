<template>
	<div class="search-select">
		<label :for="inputId" class="block text-sm font-medium text-ink">{{ label }}</label>
		<div class="relative mt-1">
			<input
				:id="inputId"
				ref="input"
				:value="query"
				role="combobox"
				:aria-expanded="open"
				:aria-controls="listId"
				:aria-activedescendant="
					open && filtered[active] ? `${listId}-${active}` : undefined
				"
				aria-autocomplete="list"
				:disabled="disabled"
				:required="required"
				:placeholder="placeholder"
				autocomplete="off"
				class="search-input"
				@input="type"
				@focus="focus"
				@blur="blur"
				@keydown="keydown"
			/>
			<span class="pointer-events-none absolute right-3 top-3 text-muted" aria-hidden="true"
				>⌄</span
			>
			<div v-if="open && !disabled" class="search-menu">
				<ul
					:id="listId"
					role="listbox"
					:aria-label="label"
					class="max-h-60 overflow-y-auto"
				>
					<li
						v-for="(option, index) in filtered"
						:id="`${listId}-${index}`"
						:key="option.value"
						role="option"
						:aria-selected="modelValue === option.value"
						class="search-option"
						:class="{ 'bg-accent-soft': active === index }"
						@pointerdown.prevent="choose(option)"
						@mousemove="active = index"
					>
						<span class="block font-medium">{{ option.label }}</span>
						<span v-if="option.description" class="block text-xs text-muted mt-0.5">{{
							option.description
						}}</span>
					</li>
				</ul>
				<p v-if="!filtered.length" class="px-3 py-3 text-sm text-muted" role="status">
					{{ emptyText }}
				</p>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, ref, useId, watch, watchEffect } from "vue";

const props = defineProps({
	modelValue: { type: String, default: "" },
	options: { type: Array, default: () => [] },
	label: { type: String, required: true },
	placeholder: { type: String, default: "Type to find an expense account" },
	emptyText: {
		type: String,
		default:
			"No matching account. Choose an existing Expense account; new ledger accounts must be created by authorized Accounts staff.",
	},
	selectionError: { type: String, default: "Choose an expense account from the suggestions." },
	disabled: Boolean,
	required: Boolean,
});
const emit = defineEmits(["update:modelValue", "change"]);
const inputId = useId(),
	listId = `${inputId}-options`;
const input = ref(null),
	query = ref(""),
	open = ref(false),
	focused = ref(false),
	active = ref(0);
const selected = computed(() => props.options.find((option) => option.value === props.modelValue));
const filtered = computed(() => {
	const term = query.value === selected.value?.label ? "" : query.value.trim().toLowerCase();
	return props.options.filter((option) =>
		`${option.label} ${option.description || ""} ${option.value}`.toLowerCase().includes(term),
	);
});
watch(
	selected,
	(option) => {
		if (option) query.value = option.label;
		else if (!focused.value) query.value = "";
	},
	{ immediate: true },
);
watchEffect(() =>
	input.value?.setCustomValidity(
		props.required && !props.disabled && !selected.value ? props.selectionError : "",
	),
);
function focus() {
	focused.value = true;
	open.value = true;
	active.value = 0;
}
function blur() {
	focused.value = false;
	open.value = false;
	if (selected.value) query.value = selected.value.label;
}
function type(event) {
	query.value = event.target.value;
	open.value = true;
	active.value = 0;
	const matches = props.options.filter(
		(option) => option.value === query.value || option.label === query.value,
	);
	const exact = matches.length === 1 ? matches[0] : undefined;
	emit("update:modelValue", exact?.value || "");
	if (exact) emit("change", exact);
}
function choose(option) {
	emit("update:modelValue", option.value);
	emit("change", option);
	query.value = option.label;
	open.value = false;
}
async function keydown(event) {
	if (event.key === "ArrowDown" || event.key === "ArrowUp") {
		event.preventDefault();
		if (!open.value) {
			open.value = true;
			active.value = 0;
		} else
			active.value = Math.max(
				0,
				Math.min(
					filtered.value.length - 1,
					active.value + (event.key === "ArrowDown" ? 1 : -1),
				),
			);
		await nextTick();
		document.getElementById(`${listId}-${active.value}`)?.scrollIntoView({ block: "nearest" });
	} else if (event.key === "Enter" && open.value) {
		event.preventDefault();
		if (filtered.value[active.value]) choose(filtered.value[active.value]);
	} else if (event.key === "Escape") {
		event.preventDefault();
		open.value = false;
		if (selected.value) query.value = selected.value.label;
	}
}
</script>

<style scoped>
.search-select {
	min-width: 0;
}
.search-input {
	@apply block w-full rounded-xl border border-line bg-surface px-3 py-2.5 pr-8 text-sm text-ink;
}
.search-input:focus-visible {
	outline: 2px solid var(--accent);
	outline-offset: 2px;
}
.search-menu {
	@apply absolute z-20 w-full mt-1 rounded-xl border border-line bg-surface shadow-lift;
}
.search-option {
	@apply px-3 py-2.5 text-sm text-ink cursor-pointer break-words;
}
</style>
