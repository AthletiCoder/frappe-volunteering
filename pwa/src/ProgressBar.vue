<template>
	<div
		class="progress-track"
		role="progressbar"
		:aria-label="`${item.title}: ${progress.label}`"
		:aria-valuenow="Math.round(progress.percent)"
		aria-valuemin="0"
		aria-valuemax="100"
	>
		<span class="progress-fill" :style="{ width: `${progress.percent}%` }"></span
		><i
			v-for="(stage, index) in progress.stages"
			:key="stage.key"
			:class="{
				done: index < progress.index || item.status === 'Completed',
				current: index === progress.index,
			}"
			:style="{
				left: `${progress.stages.length < 2 ? 0 : (index / (progress.stages.length - 1)) * 100}%`,
			}"
			:title="stage.label"
		></i>
	</div>
</template>
<script setup>
import { computed } from "vue";
import { progressOf } from "./model.js";
const props = defineProps({ item: Object });
const progress = computed(() => progressOf(props.item));
</script>
