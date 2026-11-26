<template>
	<aside class="queue-rail kit-panel" :aria-label="label">
		<header class="queue-rail__head">
			<div class="min-w-0">
				<p class="eyebrow">{{ label }}</p>
				<p class="mt-0.5 text-xs text-muted">
					<template v-if="position >= 0">{{ position + 1 }} of {{ items.length }}</template>
					<template v-else>{{ items.length }} waiting</template>
				</p>
			</div>
			<div class="flex gap-1">
				<button type="button" class="queue-rail__step" :disabled="!previous" :title="previous ? `Previous (K)` : 'No previous item'" aria-label="Previous in queue" @click="previous && $emit('open', previous.key)"><Icon name="arrow-left" size="sm" /></button>
				<button type="button" class="queue-rail__step" :disabled="!next" :title="next ? `Next (J)` : 'No next item'" aria-label="Next in queue" @click="next && $emit('open', next.key)"><Icon name="arrow-right" size="sm" /></button>
			</div>
		</header>
		<ol class="queue-rail__list">
			<li v-for="item in items" :key="item.key">
				<a
					:href="item.href"
					class="queue-rail__item"
					:class="{ 'queue-rail__item--active': item.key === activeKey }"
					:aria-current="item.key === activeKey ? 'true' : undefined"
					@click.prevent="$emit('open', item.key)"
				>
					<Avatar :name="item.person" size="sm" />
					<span class="min-w-0 flex-1">
						<span class="block truncate text-[13px] font-semibold text-ink">{{ item.person }}</span>
						<span class="block truncate text-xs text-muted">{{ item.subtitle }}</span>
					</span>
					<span v-if="item.amount" class="shrink-0 text-xs font-semibold tabular-nums text-ink">{{ item.amount }}</span>
				</a>
			</li>
		</ol>
		<p class="queue-rail__keys" aria-hidden="true"><span class="key">J</span><span class="key">K</span> move · <span class="key">Esc</span> back to queue</p>
	</aside>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from "vue";
import Avatar from "./Avatar.vue";
import Icon from "./Icon.vue";

const props = defineProps({
	// [{ key, person, subtitle, amount, href }]
	items: { type: Array, default: () => [] },
	activeKey: { type: String, default: "" },
	label: { type: String, default: "Queue" },
});
const emit = defineEmits(["open", "close"]);

const position = computed(() => props.items.findIndex((item) => item.key === props.activeKey));
const next = computed(() => (position.value >= 0 ? props.items[position.value + 1] : props.items[0]) || null);
const previous = computed(() => (position.value > 0 ? props.items[position.value - 1] : null));

function typing(target) {
	return target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
}
function onKeydown(event) {
	if (event.metaKey || event.ctrlKey || event.altKey || typing(event.target) || document.querySelector('[role="dialog"]')) return;
	const key = event.key.toLowerCase();
	if (key === "j" && next.value) { event.preventDefault(); emit("open", next.value.key); }
	else if (key === "k" && previous.value) { event.preventDefault(); emit("open", previous.value.key); }
	else if (key === "escape") emit("close");
}
onMounted(() => window.addEventListener("keydown", onKeydown));
onUnmounted(() => window.removeEventListener("keydown", onKeydown));
</script>

<style scoped>
.queue-rail { display: flex; max-height: calc(100vh - 7rem); flex-direction: column; overflow: hidden; }
.queue-rail__head { display: flex; align-items: center; justify-content: space-between; gap: 0.5rem; border-bottom: 1px solid var(--line); padding: 0.875rem 1rem; }
.queue-rail__step { display: inline-flex; width: 2rem; height: 2rem; align-items: center; justify-content: center; border-radius: 10px; border: 1px solid var(--line); color: var(--ink-2); transition: background-color var(--dur-fast) ease; }
.queue-rail__step:hover:not(:disabled) { background: var(--navy-50); color: var(--navy-900); }
.queue-rail__step:disabled { opacity: 0.4; cursor: not-allowed; }
.queue-rail__list { min-height: 0; flex: 1; overflow-y: auto; padding: 0.375rem; }
.queue-rail__item { position: relative; display: flex; align-items: center; gap: 0.625rem; border-radius: 12px; padding: 0.5rem 0.625rem; transition: background-color var(--dur-fast) ease; }
.queue-rail__item:hover { background: var(--soft); }
.queue-rail__item--active, .queue-rail__item--active:hover { background: var(--navy-50); box-shadow: inset 0 0 0 1px var(--navy-100); }
.queue-rail__item--active::before { content: ""; position: absolute; left: 0; top: 0.625rem; bottom: 0.625rem; width: 3px; border-radius: 3px; background: var(--navy-900); }
.queue-rail__keys { border-top: 1px solid var(--line); padding: 0.5rem 1rem; font-size: 0.6875rem; color: var(--muted); }
.queue-rail__keys .key { margin-right: 0.125rem; border-radius: 4px; border: 1px solid var(--line); background: var(--surface); padding: 0 0.3rem; font-family: inherit; font-size: 0.625rem; color: var(--ink-2); }
</style>
