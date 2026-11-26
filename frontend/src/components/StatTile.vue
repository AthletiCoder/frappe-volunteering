<template>
	<component :is="to ? RouterLink : 'div'" :to="to || undefined" class="stat-tile group" :class="{ 'stat-tile--attention': attention }">
		<span class="flex items-center justify-between gap-2">
			<span class="stat-tile__label">{{ label }}</span>
			<span class="stat-tile__icon"><Icon :name="icon" size="sm" /></span>
		</span>
		<span class="stat-tile__value">{{ value }}</span>
		<span v-if="hint" class="stat-tile__hint">{{ hint }}</span>
	</component>
</template>

<script setup>
import { RouterLink } from "vue-router";
import Icon from "./Icon.vue";

defineProps({
	label: { type: String, required: true },
	value: { type: [String, Number], required: true },
	hint: { type: String, default: "" },
	icon: { type: String, default: "check" },
	to: { type: [String, Object], default: "" },
	attention: Boolean,
});
</script>
