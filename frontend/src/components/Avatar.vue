<template>
	<span class="kit-avatar" :class="[SIZES[size] || SIZES.md, TONE_CLASSES[toneName] || TONE_CLASSES.navy]" aria-hidden="true">{{ initials }}</span>
</template>

<script setup>
import { computed } from "vue";

const props = defineProps({
	name: { type: String, default: "" },
	size: { type: String, default: "md" },
	tone: { type: String, default: "" },
});
// Full class names written out so Tailwind keeps them in the build.
const SIZES = { sm: "kit-avatar--sm", md: "kit-avatar--md", lg: "kit-avatar--lg" };
const TONE_CLASSES = { navy: "kit-avatar--navy", teal: "kit-avatar--teal", plum: "kit-avatar--plum", amber: "kit-avatar--amber", rose: "kit-avatar--rose", slate: "kit-avatar--slate" };
const TONES = Object.keys(TONE_CLASSES);
const initials = computed(() => {
	const words = String(props.name || "").replace(/[^\p{L}\p{N}\s]/gu, " ").trim().split(/\s+/).filter(Boolean);
	return (words.slice(0, 2).map((word) => word[0]).join("") || "•").toUpperCase();
});
const toneName = computed(() => {
	if (props.tone) return props.tone;
	let hash = 0;
	for (const char of String(props.name || "")) hash = (hash * 31 + char.codePointAt(0)) >>> 0;
	return TONES[hash % TONES.length];
});
</script>
