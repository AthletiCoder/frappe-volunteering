<template>
	<ol class="tracker" :aria-label="label">
		<li v-for="(step, index) in steps" :key="step.label" class="tracker__step" :class="`tracker__step--${step.state}`" :aria-current="step.state === 'current' || step.state === 'attention' ? 'step' : undefined">
			<span class="tracker__marker" aria-hidden="true">
				<svg v-if="step.state === 'done'" viewBox="0 0 16 16"><path d="M4 8.5 6.5 11 12 5.5" /></svg>
				<svg v-else-if="step.state === 'stopped'" viewBox="0 0 16 16"><path d="M5 5l6 6M11 5l-6 6" /></svg>
				<span v-else-if="step.state === 'attention'" class="text-[11px] font-bold">!</span>
				<span v-else class="text-[11px] font-semibold">{{ index + 1 }}</span>
			</span>
			<span class="tracker__text">
				<span class="tracker__label">{{ step.label }}</span>
				<span v-if="step.note" class="tracker__note">{{ step.note }}</span>
				<span class="sr-only">{{ STATE_TEXT[step.state] }}</span>
			</span>
		</li>
	</ol>
</template>

<script setup>
defineProps({
	steps: { type: Array, required: true },
	label: { type: String, default: "Progress" },
});
const STATE_TEXT = { done: "(completed)", current: "(in progress)", attention: "(needs your action)", stopped: "(stopped)", todo: "(not started)" };
</script>

<style scoped>
.tracker { display: grid; gap: 0; }
.tracker__step { position: relative; display: flex; gap: 0.75rem; padding-bottom: 1rem; min-width: 0; }
.tracker__step:last-child { padding-bottom: 0; }
/* Vertical connector on phones */
.tracker__step:not(:last-child)::after {
	content: "";
	position: absolute;
	left: 0.8125rem;
	top: 1.75rem;
	bottom: 0.25rem;
	width: 2px;
	border-radius: 2px;
	background: var(--line);
}
.tracker__step--done:not(:last-child)::after { background: var(--ok); }
.tracker__marker {
	position: relative;
	z-index: 1;
	display: inline-flex;
	width: 1.75rem;
	height: 1.75rem;
	flex-shrink: 0;
	align-items: center;
	justify-content: center;
	border-radius: 999px;
	border: 2px solid var(--line-strong);
	background: var(--surface);
	color: var(--muted);
}
.tracker__marker svg { width: 0.875rem; height: 0.875rem; fill: none; stroke: currentColor; stroke-width: 2.25; stroke-linecap: round; stroke-linejoin: round; }
.tracker__step--done .tracker__marker { border-color: var(--ok); background: var(--ok); color: #fff; }
.tracker__step--current .tracker__marker { border-color: var(--navy-900); background: var(--navy-900); color: #fff; box-shadow: 0 0 0 4px var(--navy-50); }
.tracker__step--attention .tracker__marker { border-color: var(--warn); background: var(--warn); color: #fff; box-shadow: 0 0 0 4px var(--warn-soft); }
.tracker__step--stopped .tracker__marker { border-color: var(--bad); background: var(--bad); color: #fff; }
.tracker__text { display: flex; min-width: 0; flex-direction: column; padding-top: 0.2rem; }
.tracker__label { font-size: 0.8125rem; font-weight: 600; line-height: 1.3; color: var(--muted); }
.tracker__step--done .tracker__label { color: var(--ink-2); }
.tracker__step--current .tracker__label, .tracker__step--attention .tracker__label, .tracker__step--stopped .tracker__label { color: var(--ink); }
.tracker__note { margin-top: 0.125rem; font-size: 0.75rem; line-height: 1.35; color: var(--muted); }
.tracker__step--attention .tracker__note { color: var(--warn); }
.tracker__step--stopped .tracker__note { color: var(--bad); }

/* Horizontal from tablets up */
@media (min-width: 640px) {
	.tracker { grid-auto-columns: minmax(0, 1fr); grid-auto-flow: column; }
	.tracker__step { flex-direction: column; align-items: center; gap: 0.5rem; padding: 0 0.25rem; text-align: center; }
	.tracker__step:not(:last-child)::after { left: calc(50% + 1.125rem); right: calc(-50% + 1.125rem); top: 0.8125rem; bottom: auto; width: auto; height: 2px; }
	.tracker__text { align-items: center; padding-top: 0; }
}
@media (prefers-reduced-motion: no-preference) {
	.tracker__step--current .tracker__marker { animation: tracker-pulse 2.4s ease-in-out infinite; }
}
@keyframes tracker-pulse { 0%, 100% { box-shadow: 0 0 0 4px var(--navy-50); } 50% { box-shadow: 0 0 0 7px var(--navy-50); } }
</style>
