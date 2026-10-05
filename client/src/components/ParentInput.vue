<template>
  <div class="parent-input">
    <!-- existing parents: click to pick / unpick -->
    <div v-if="options.length" class="d-flex flex-wrap gap-1 mb-1">
      <button
        v-for="p in shownOptions"
        :key="p"
        type="button"
        class="btn btn-sm parent-option"
        :class="isPicked(p) ? 'btn-primary' : 'btn-outline-secondary'"
        :aria-pressed="isPicked(p)"
        @click="toggle(p)"
      >
        <i class="fa" :class="isPicked(p) ? 'fa-check-square-o' : 'fa-square-o'" /> {{ p }}
      </button>
      <span v-if="!shownOptions.length" class="small text-muted">{{ $t('parents.noMatch') }}</span>
    </div>

    <!-- filter the list, or type a new one when it is not there -->
    <div class="input-group input-group-sm">
      <span class="input-group-text"><i class="fa" :class="options.length ? 'fa-search' : 'fa-folder-o'" /></span>
      <input
        v-model="text"
        class="form-control"
        :placeholder="options.length ? $t('parents.findOrNew') : $t('parents.firstOne')"
        @keydown.enter.prevent="onEnter"
      />
      <button
        v-if="newName"
        type="button"
        class="btn btn-outline-primary"
        @click="addNew"
      >
        <i class="fa fa-plus" /> {{ $t('parents.addNew', { name: newName }) }}
      </button>
    </div>
    <div v-if="modelValue.length" class="small text-muted mt-1">
      {{ $t('parents.picked', { names: modelValue.join('、') }) }}
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { allParents, parseParents } from "@/libs/parents";

// parents of all the user's categories, fetched once per page (annotator)
let everyParent = null;
function loadEveryParent() {
  if (!everyParent) {
    everyParent = axios.get("/api/category/").then(r => allParents(r.data || [])).catch(() => []);
  }
  return everyParent;
}

/**
 * Pick parent categories from the ones already in use (click to toggle);
 * typing filters them, and offers to add a new one only when it does not exist.
 */
export default {
  name: "ParentInput",
  props: {
    modelValue: { type: Array, default: () => [] },
    /** parent names already in use */
    known: { type: Array, default: () => [] },
    /** also offer the parents of all the user's categories (fetched once) */
    fetchKnown: { type: Boolean, default: false }
  },
  emits: ["update:modelValue"],
  data() {
    return { text: "", fetched: [] };
  },
  created() {
    if (this.fetchKnown) loadEveryParent().then(list => (this.fetched = list));
  },
  computed: {
    options() {
      return parseParents([...this.known, ...this.fetched, ...this.modelValue])
        .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }));
    },
    shownOptions() {
      const q = this.text.trim().toLowerCase();
      return q ? this.options.filter(p => p.toLowerCase().includes(q)) : this.options;
    },
    /** the typed name, if no parent of that name exists yet */
    newName() {
      const name = this.text.trim();
      if (!name) return "";
      return this.options.some(p => p.toLowerCase() === name.toLowerCase()) ? "" : name;
    }
  },
  methods: {
    isPicked(p) {
      return this.modelValue.includes(p);
    },
    toggle(p) {
      this.$emit("update:modelValue", this.isPicked(p) ? this.modelValue.filter(x => x !== p) : [...this.modelValue, p]);
    },
    addNew() {
      const names = parseParents(this.newName);
      this.text = "";
      if (names.length) this.$emit("update:modelValue", parseParents([...this.modelValue, ...names]));
    },
    onEnter() {
      if (this.newName) return this.addNew();
      // Enter on a filtered list with one match picks it
      if (this.shownOptions.length === 1) {
        if (!this.isPicked(this.shownOptions[0])) this.toggle(this.shownOptions[0]);
        this.text = "";
      }
    }
  }
};
</script>

<style scoped>
.parent-option {
  padding: 0 8px;
  font-size: 0.8rem;
  border-radius: 999px;
}
</style>
