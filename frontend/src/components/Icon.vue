<template>
	<svg
		xmlns="http://www.w3.org/2000/svg"
		:class="cn('shrink-0', sizeClass)"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.8"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
	>
		<path v-if="name === 'home'" d="M4 10.5 12 4l8 6.5V20a1 1 0 0 1-1 1h-5v-6H10v6H5a1 1 0 0 1-1-1z" />
		<path v-else-if="name === 'check'" d="M9 11.5 11 14l4-5M7 4h10a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z" />
		<path v-else-if="name === 'wallet'" d="M4 7h16v12H4zM4 7a3 3 0 0 1 3-3h10M16 13h2" />
		<path v-else-if="name === 'chart'" d="M4 19V5M4 19h16M8 16v-5M12 16V8M16 16v-3" />
		<path v-else-if="name === 'bell'" d="M6 17h12l-1.2-2.2A6 6 0 0 1 6.8 9.5L6 17zM10 19a2 2 0 0 0 4 0" />
		<path v-else-if="name === 'help'" d="M12 18h.01M9.1 9a3 3 0 1 1 4.2 2.7c-.8.4-1.3 1-1.3 1.8V14" />
		<circle v-if="name === 'help'" cx="12" cy="12" r="9" />
		<path v-else-if="name === 'desk'" d="M5 19V9h14v10M9 19v-4h6v4M5 9l7-5 7 5" />
		<path v-else-if="name === 'clock'" d="M12 7v5l3 2M12 21a9 9 0 1 1 0-18 9 9 0 0 1 0 18z" />
		<path v-else-if="name === 'sun'" d="M12 4v2M12 18v2M5 12H3M21 12h-2M6 6l1.5 1.5M16.5 16.5 18 18M18 6l-1.5 1.5M7.5 16.5 6 18M12 8a4 4 0 1 1 0 8 4 4 0 0 1 0-8z" />
		<path v-else-if="name === 'leave'" d="M8 7V5a1 1 0 0 1 1-1h10v16H9a1 1 0 0 1-1-1v-2M8 12H3m0 0 3-3M3 12l3 3" />
		<path v-else-if="name === 'fix'" d="M12 8V4M12 20v-4M8 12H4M20 12h-4M7 7l-2-2M19 19l-2-2M17 7l2-2M5 19l2-2" />
		<path v-else-if="name === 'vendor'" d="M4 10h16l-1 9H5l-1-9zM8 10V7a4 4 0 0 1 8 0v3" />
		<path v-else-if="name === 'advance'" d="M12 4v16M8 8h6a3 3 0 0 1 0 6H9a3 3 0 0 0 0 6h7" />
		<path v-else-if="name === 'claim'" d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8zM14 3v5h5" />
		<path v-else-if="name === 'book'" d="M5 5h11a2 2 0 0 1 2 2v12H7a2 2 0 0 0-2 2z" />
		<path v-else-if="name === 'people'" d="M16 19v-1a3 3 0 0 0-3-3H7a3 3 0 0 0-3 3v1M10 12a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM20 19v-1a3 3 0 0 0-2-2.8M16 6.2a3 3 0 0 1 0 5.6" />
		<path v-else-if="name === 'spark'" d="M12 3v4M12 17v4M5 12H3M21 12h-2M7 7 5.5 5.5M18.5 18.5 17 17M17 7l1.5-1.5M7 17l-1.5 1.5" />
		<path v-else-if="name === 'menu'" d="M5 7h14M5 12h14M5 17h14" />
		<path v-else-if="name === 'close'" d="M7 7l10 10M17 7 7 17" />
		<path
			v-else-if="name === 'moon'"
			fill="currentColor"
			stroke="none"
			d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"
		/>
		<path v-else-if="name === 'refresh'" d="M4 12a8 8 0 0 1 13.7-5.7L20 8M20 12a8 8 0 0 1-13.7 5.7L4 16M20 4v4h-4M4 20v-4h4" />
		<circle v-else cx="12" cy="12" r="3" />
	</svg>
</template>

<script setup>
import { computed } from "vue";
import { cn } from "../lib/cn";

const props = defineProps({
	name: { type: String, required: true },
	size: { type: String, default: "md" },
});

const sizeClass = computed(() => {
	if (props.size === "sm") return "w-4 h-4";
	if (props.size === "lg") return "w-6 h-6";
	return "w-5 h-5";
});
</script>
