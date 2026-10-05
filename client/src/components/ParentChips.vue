<template>
  <div v-if="groups.length" class="parent-chips d-flex flex-wrap align-items-center gap-1">
    <span class="small text-muted me-1"><i class="fa fa-folder-open-o" /> {{ $t('parents.quick') }}</span>
    <button
      v-for="g in groups"
      :key="g.parent"
      type="button"
      class="btn btn-sm parent-chip"
      :class="g.state === 'all' ? 'btn-primary' : g.state === 'some' ? 'btn-outline-primary partial' : 'btn-outline-secondary'"
      :title="g.items.map(c => c.name).join('、')"
      @click="toggle(g)"
    >
      <i class="fa" :class="g.state === 'all' ? 'fa-check-square-o' : g.state === 'some' ? 'fa-minus-square-o' : 'fa-square-o'" />
      {{ g.parent }}
      <span class="small opacity-75">{{ g.chosen }}/{{ g.items.length }}</span>
    </button>
  </div>
</template>

<script>
import { groupByParent } from "@/libs/parents";

/**
 * One button per parent category: adds all its categories to the selection
 * (or removes them when they are all selected already).
 */
export default {
  name: "ParentChips",
  props: {
    categories: { type: Array, required: true },
    selected: { type: Array, required: true },
    /** what the selection holds for a category (its id, or its name) */
    keyOf: { type: Function, default: c => c.id }
  },
  emits: ["update:selected"],
  computed: {
    groups() {
      const chosen = new Set(this.selected);
      return groupByParent(this.categories)
        .filter(g => g.parent !== null)
        .map(g => {
          const n = g.items.filter(c => chosen.has(this.keyOf(c))).length;
          return { ...g, chosen: n, state: n === 0 ? "none" : n === g.items.length ? "all" : "some" };
        });
    }
  },
  methods: {
    toggle(group) {
      const keys = group.items.map(this.keyOf);
      if (group.state === "all") {
        this.$emit("update:selected", this.selected.filter(k => !keys.includes(k)));
      } else {
        this.$emit("update:selected", [...this.selected, ...keys.filter(k => !this.selected.includes(k))]);
      }
    }
  }
};
</script>

<style scoped>
.parent-chip {
  padding: 0 8px;
  font-size: 0.8rem;
  border-radius: 999px;
}
</style>
