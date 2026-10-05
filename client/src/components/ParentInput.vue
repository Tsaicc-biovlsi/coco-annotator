<template>
  <div class="parent-input form-control form-control-sm d-flex flex-wrap align-items-center gap-1" @click="$refs.input.focus()">
    <span v-for="p in modelValue" :key="p" class="parent-tag">
      <i class="fa fa-folder-o" /> {{ p }}
      <button type="button" class="btn-close btn-close-sm" :aria-label="$t('parents.remove')" @click.stop="remove(p)" />
    </span>
    <input
      ref="input"
      v-model="text"
      :list="listId"
      class="flex-grow-1"
      :placeholder="modelValue.length ? '' : $t('parents.placeholder')"
      @keydown.enter.prevent="add"
      @keydown="onKey"
      @blur="add"
      @change="add"
    />
    <datalist :id="listId">
      <option v-for="p in suggestions" :key="p" :value="p" />
    </datalist>
  </div>
</template>

<script>
import { parseParents } from "@/libs/parents";

let counter = 0;

/** Parent categories as tags: type a name and press Enter (or comma); existing parents are suggested. */
export default {
  name: "ParentInput",
  props: {
    modelValue: { type: Array, default: () => [] },
    /** parent names already in use, offered as suggestions */
    known: { type: Array, default: () => [] }
  },
  emits: ["update:modelValue"],
  data() {
    counter += 1;
    return { text: "", listId: `parents-${counter}` };
  },
  computed: {
    suggestions() {
      return this.known.filter(p => !this.modelValue.includes(p));
    }
  },
  methods: {
    add() {
      const names = parseParents(this.text);
      this.text = "";
      if (!names.length) return;
      this.$emit("update:modelValue", parseParents([...this.modelValue, ...names]));
    },
    remove(p) {
      this.$emit("update:modelValue", this.modelValue.filter(x => x !== p));
    },
    onKey(event) {
      if (event.key === "," || event.key === "，" || event.key === "、") {
        event.preventDefault();
        this.add();
      } else if (event.key === "Backspace" && !this.text && this.modelValue.length) {
        this.remove(this.modelValue[this.modelValue.length - 1]);
      }
    }
  }
};
</script>

<style scoped>
.parent-input {
  min-height: 31px;
  cursor: text;
  height: auto;
}
.parent-input input {
  border: none;
  outline: none;
  min-width: 120px;
  background: transparent;
  color: inherit;
  font-size: 0.875rem;
}
.parent-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #e7f0fb;
  color: #1d5ea8;
  border-radius: 4px;
  padding: 0 4px 0 6px;
  font-size: 0.8rem;
}
.btn-close-sm {
  width: 0.5em;
  height: 0.5em;
  padding: 2px;
}
</style>
