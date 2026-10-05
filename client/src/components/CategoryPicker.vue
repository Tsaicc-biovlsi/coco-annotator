<template>
  <div class="category-picker">
    <!-- add new categories (several at once) -->
    <div class="input-group input-group-sm mb-2">
      <input
        v-model="newText"
        class="form-control"
        :placeholder="$t('categoryPicker.addPlaceholder')"
        @keydown.enter.prevent="addNew"
        @paste="onPaste"
      />
      <button type="button" class="btn btn-outline-primary" :disabled="!newText.trim()" @click="addNew">
        <i class="fa fa-plus" /> {{ $t('categoryPicker.add') }}
      </button>
    </div>

    <div class="d-flex align-items-center flex-wrap gap-1 mb-1">
      <span class="small text-muted me-auto">
        {{ $t('categoryPicker.selected', { n: modelValue.length, total: rows.length }) }}
      </span>
      <button type="button" class="btn btn-outline-secondary btn-sm py-0" :disabled="!rows.length" @click="select(rows.map(r => r.name))">
        {{ $t('exportCategories.all') }}
      </button>
      <button type="button" class="btn btn-outline-secondary btn-sm py-0" :disabled="!modelValue.length" @click="select([])">
        {{ $t('exportCategories.none') }}
      </button>
    </div>

    <input
      v-if="rows.length > 8"
      v-model="filter"
      class="form-control form-control-sm mb-1"
      :placeholder="$t('exportCategories.search')"
    />

    <ul class="list-group picker-list">
      <li
        v-for="(row, position) in visibleRows"
        :key="row.name"
        class="list-group-item d-flex align-items-center gap-2 py-1 px-2"
        :class="{ 'text-muted': !isSelected(row.name) }"
      >
        <input
          :id="'catpick-' + position"
          type="checkbox"
          class="form-check-input m-0 flex-shrink-0"
          :checked="isSelected(row.name)"
          @change="toggle(row.name)"
        />
        <span
          class="badge class-index"
          :class="isSelected(row.name) ? 'text-bg-primary' : 'text-bg-light text-muted'"
          :title="$t('categoryPicker.order')"
        >{{ isSelected(row.name) ? modelValue.indexOf(row.name) : '–' }}</span>
        <span class="color-dot flex-shrink-0" :style="{ backgroundColor: row.color || '#adb5bd' }" />
        <label :for="'catpick-' + position" class="flex-grow-1 mb-0 text-truncate" :title="row.name">{{ row.name }}</label>
        <span v-if="row.isNew" class="badge text-bg-success">{{ $t('categoryPicker.new') }}</span>
        <span v-if="isSelected(row.name) && !filter" class="btn-group btn-group-sm flex-shrink-0">
          <button
            type="button"
            class="btn btn-link btn-sm p-0 px-1"
            :disabled="modelValue.indexOf(row.name) === 0"
            :title="$t('exportCategories.moveUp')"
            @click="move(row.name, -1)"
          ><i class="fa fa-chevron-up" /></button>
          <button
            type="button"
            class="btn btn-link btn-sm p-0 px-1"
            :disabled="modelValue.indexOf(row.name) === modelValue.length - 1"
            :title="$t('exportCategories.moveDown')"
            @click="move(row.name, 1)"
          ><i class="fa fa-chevron-down" /></button>
        </span>
        <button
          v-if="row.isNew"
          type="button"
          class="btn btn-link btn-sm p-0 text-danger"
          :title="$t('categoryPicker.remove')"
          @click="removeNew(row.name)"
        ><i class="fa fa-times" /></button>
      </li>
      <li v-if="!visibleRows.length" class="list-group-item small text-muted">
        {{ rows.length ? $t('exportCategories.noMatch') : $t('categoryPicker.empty') }}
      </li>
    </ul>
    <div class="form-text">{{ $t('categoryPicker.hint') }}</div>
  </div>
</template>

<script>
/**
 * Pick the categories of a new dataset: tick existing ones, add new names
 * (comma / line separated, pasting a list works), set their order.
 * v-model is the ordered list of selected names.
 */
export default {
  name: "CategoryPicker",
  props: {
    /** existing categories [{ name, color }] */
    categories: { type: Array, default: () => [] },
    modelValue: { type: Array, default: () => [] }
  },
  emits: ["update:modelValue"],
  data() {
    return { newText: "", filter: "", added: [] };
  },
  computed: {
    /** selected first (in their order), then the rest by name */
    rows() {
      const existing = new Map(this.categories.map(c => [c.name, c]));
      const all = [
        ...this.added.filter(n => !existing.has(n)).map(name => ({ name, isNew: true })),
        ...this.categories.map(c => ({ name: c.name, color: c.color, isNew: false }))
      ];
      const byName = new Map(all.map(r => [r.name, r]));
      const selected = this.modelValue.filter(n => byName.has(n)).map(n => byName.get(n));
      const rest = all.filter(r => !this.modelValue.includes(r.name))
        .sort((a, b) => a.name.localeCompare(b.name, undefined, { numeric: true }));
      return [...selected, ...rest];
    },
    visibleRows() {
      const q = this.filter.trim().toLowerCase();
      return q ? this.rows.filter(r => r.name.toLowerCase().includes(q)) : this.rows;
    }
  },
  methods: {
    isSelected(name) {
      return this.modelValue.includes(name);
    },
    select(names) {
      this.$emit("update:modelValue", [...names]);
    },
    toggle(name) {
      this.select(this.isSelected(name) ? this.modelValue.filter(n => n !== name) : [...this.modelValue, name]);
    },
    move(name, step) {
      const order = [...this.modelValue];
      const from = order.indexOf(name);
      const to = from + step;
      if (to < 0 || to >= order.length) return;
      [order[from], order[to]] = [order[to], order[from]];
      this.select(order);
    },
    /** "a, b、c" or one per line -> names (trimmed, unique) */
    parse(text) {
      return [...new Set(String(text).split(/[\n\r,，、;；\t]+/).map(s => s.trim()).filter(Boolean))];
    },
    addNew() {
      const names = this.parse(this.newText);
      if (!names.length) return;
      const known = new Set(this.categories.map(c => c.name));
      names.forEach(n => {
        if (!known.has(n) && !this.added.includes(n)) this.added.push(n);
      });
      this.select([...this.modelValue, ...names.filter(n => !this.modelValue.includes(n))]);
      this.newText = "";
    },
    onPaste(event) {
      // a pasted list (several lines) is added straight away
      const text = (event.clipboardData || window.clipboardData).getData("text");
      if (/[\n\r]/.test(text)) {
        event.preventDefault();
        this.newText = text;
        this.addNew();
      }
    },
    removeNew(name) {
      this.added = this.added.filter(n => n !== name);
      this.select(this.modelValue.filter(n => n !== name));
    },
    reset() {
      this.added = [];
      this.newText = "";
      this.filter = "";
    }
  }
};
</script>

<style scoped>
.picker-list {
  max-height: 240px;
  overflow-y: auto;
}
.color-dot {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
}
.class-index {
  min-width: 26px;
}
</style>
