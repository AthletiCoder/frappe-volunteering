<template>
	<div v-if="open" class="app-scrim anim-fade fixed inset-0 z-50 flex items-end justify-center sm:items-start sm:px-4 sm:pt-[10vh]" @click.self="$emit('close')">
		<section
			ref="panel"
			class="new-sheet anim-sheet w-full max-w-2xl overflow-hidden bg-surface shadow-pop"
			role="dialog"
			aria-modal="true"
			aria-labelledby="new-sheet-title"
			tabindex="-1"
			@keydown.esc="$emit('close')"
		>
			<header class="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
				<div>
					<h2 id="new-sheet-title" class="font-display text-lg font-semibold text-ink">Start something new</h2>
					<p class="text-sm text-muted">Pick a request to open its form.</p>
				</div>
				<button type="button" class="btn-ghost" aria-label="Close" @click="$emit('close')"><Icon name="close" /></button>
			</header>
			<div class="max-h-[70vh] overflow-y-auto p-3 sm:p-4">
				<p v-if="!groups.length" class="px-2 py-8 text-center text-sm text-muted">There is nothing you can start from here yet.</p>
				<div v-for="group in groups" :key="group.title" class="new-group">
					<p class="eyebrow px-2 pb-1.5 pt-2">{{ group.title }}</p>
					<div class="grid grid-cols-1 gap-1 sm:grid-cols-2">
						<a v-for="item in group.items" :key="item.id" :href="item.href" class="new-item group" @click="$emit('close')">
							<span class="new-item__icon"><Icon :name="item.icon" size="sm" /></span>
							<span class="min-w-0 flex-1">
								<span class="block text-sm font-semibold text-ink">{{ item.label }}</span>
								<span v-if="item.hint" class="block truncate text-xs text-muted">{{ item.hint }}</span>
							</span>
							<Icon name="arrow-right" size="sm" class="new-item__arrow" />
						</a>
					</div>
				</div>
			</div>
		</section>
	</div>
</template>

<script setup>
import { nextTick, ref, watch } from "vue";
import Icon from "./Icon.vue";

const props = defineProps({
	open: Boolean,
	groups: { type: Array, default: () => [] },
});
defineEmits(["close"]);
const panel = ref(null);
watch(
	() => props.open,
	async (value) => {
		if (!value) return;
		await nextTick();
		(panel.value?.querySelector(".new-item") || panel.value)?.focus();
	},
);
</script>

<style scoped>
.new-sheet { border-radius: 20px 20px 0 0; padding-bottom: env(safe-area-inset-bottom); }
@media (min-width: 640px) { .new-sheet { border-radius: 20px; } }
.new-group + .new-group { margin-top: 0.5rem; }
.new-item {
	display: flex;
	align-items: center;
	gap: 0.75rem;
	border-radius: 14px;
	padding: 0.625rem 0.75rem;
	transition: background-color var(--dur-fast) ease;
}
.new-item:hover, .new-item:focus-visible { background: var(--navy-50); outline: none; }
.new-item__icon {
	display: inline-flex;
	width: 2.25rem;
	height: 2.25rem;
	flex-shrink: 0;
	align-items: center;
	justify-content: center;
	border-radius: 10px;
	background: var(--soft);
	color: var(--navy-900);
	transition: background-color var(--dur-fast) ease, color var(--dur-fast) ease;
}
.new-item:hover .new-item__icon, .new-item:focus-visible .new-item__icon { background: var(--navy-900); color: #fff; }
.new-item__arrow { color: var(--muted); opacity: 0; transform: translateX(-4px); transition: opacity var(--dur-fast) ease, transform var(--dur) var(--ease-out); }
.new-item:hover .new-item__arrow, .new-item:focus-visible .new-item__arrow { opacity: 1; transform: none; }
.anim-sheet { animation: sheet-up 260ms var(--ease-out) both; }
@media (min-width: 640px) { .anim-sheet { animation-name: dialog-in; } }
@keyframes sheet-up { from { transform: translateY(24px); opacity: 0; } to { transform: none; opacity: 1; } }
@media (prefers-reduced-motion: reduce) { .anim-sheet { animation: none; } }
</style>
