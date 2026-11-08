<template>
    <fieldset class="tracker-picker" :disabled="disabled">
        <legend>Attachments <span v-if="modelValue.length">({{ modelValue.length }}/5)</span></legend>
        <p>PDF, images, text, Word or Excel · up to five files · 10 MB each.</p>
        <label class="tracker-choose">Select supporting documents<input aria-label="Tracker attachments" type="file" multiple
            accept=".pdf,.png,.jpg,.jpeg,.gif,.webp,.txt,.csv,.docx,.xlsx" @change="choose" /></label>
        <p v-if="error" role="alert" class="tracker-error">{{ error }}</p>
        <ul v-if="modelValue.length">
            <li v-for="(file, index) in modelValue" :key="`${index}:${file.name}`">
                <span>{{ file.name }}<small>{{ sizeLabel(file.size) }}</small></span>
                <button type="button" :aria-label="`Remove ${file.name}`" @click="remove(index)">Remove</button>
            </li>
        </ul>
    </fieldset>
</template>
<script setup>
import { ref } from 'vue';
const props = defineProps({modelValue: {type: Array, default: () => []}, disabled: Boolean});
const emit = defineEmits(['update:modelValue']);
const error = ref('');
const allowed = new Set(['pdf','png','jpg','jpeg','gif','webp','txt','csv','docx','xlsx']);
function sizeLabel(size) {return size >= 1048576 ? `${(size / 1048576).toFixed(1)} MB` : size >= 1024 ? `${Math.ceil(size / 1024)} KB` : `${size} B`;}
function choose(event) {
    const selected = Array.from(event.target.files || []);
    event.target.value = '';
    if (props.modelValue.length + selected.length > 5) {error.value = 'Choose at most five files per update.';return;}
    if (selected.some(file => !file.size || file.size > 10485760)) {error.value = 'Choose non-empty files up to 10 MB each.';return;}
    if (selected.some(file => file.name.length > 180 || !allowed.has(file.name.split('.').pop().toLowerCase()))) {error.value = 'Choose a PDF, image, text, Word or Excel file with a name up to 180 characters.';return;}
    error.value = ''; emit('update:modelValue', [...props.modelValue, ...selected]);
}
function remove(index) {error.value='';emit('update:modelValue', props.modelValue.filter((_, i) => i !== index));}
</script>
<style scoped>
.tracker-picker { display: grid; gap: 10px; min-width: 0; padding: 14px; border: 1px solid #dce5e2; border-radius: 12px; }
.tracker-picker legend { padding: 0 5px; font-size: 14px; line-height: 1.5; font-weight: 600; }
.tracker-picker p { margin: 0; font-size: 12px; line-height: 1.6; color: #637378; }
.tracker-choose { display: grid; gap: 7px; font-size: 14px; }
.tracker-choose input { width: 100%; min-width: 0; font-size: 12px; }
.tracker-choose input::file-selector-button { margin-right: 9px; border: 1px solid #c9ddd6; border-radius: 8px; padding: 8px 11px; background: #edf6f2; color: #146b58; font: inherit; font-weight: 600; cursor: pointer; }
.tracker-picker ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 9px; }
.tracker-picker li { display: flex; align-items: center; gap: 12px; padding: 10px; border-radius: 8px; background: #fff; }
.tracker-picker li > span { flex: 1; min-width: 0; overflow-wrap: anywhere; }
.tracker-picker small { display: block; color: #637378; margin-top: 4px; }
.tracker-picker button { color: #a52e42; font-size: 12px; padding: 8px 0; }
.tracker-picker .tracker-error { color: #a52e42; }
</style>
