<template>
  <div class="export-augment">
    <div class="form-check d-flex align-items-center gap-2 ps-0">
      <input
        id="exportAugmentOn"
        type="checkbox"
        class="form-check-input m-0"
        :checked="modelValue.enabled"
        @change="set({ enabled: $event.target.checked })"
      />
      <label class="form-check-label fw-semibold mb-0" for="exportAugmentOn">{{ $t('exportAugment.title') }}</label>
    </div>
    <div v-if="!modelValue.enabled" class="form-text mt-1">{{ $t('exportAugment.off') }}</div>

    <template v-else>
      <div class="d-flex align-items-center gap-2 mt-2">
        <label class="small mb-0" for="exportAugmentCopies">{{ $t('exportAugment.copies') }}</label>
        <select
          id="exportAugmentCopies"
          class="form-select form-select-sm w-auto"
          :value="modelValue.copies"
          @change="set({ copies: Number($event.target.value) })"
        >
          <option v-for="n in 5" :key="n" :value="n">{{ n }}</option>
        </select>
        <span class="small text-muted">{{ $t('exportAugment.copiesHint') }}</span>
      </div>

      <div class="ops mt-2">
        <div v-for="op in OPS" :key="op.key" class="op">
          <div class="form-check d-flex align-items-center gap-2 ps-0 mb-0">
            <input
              :id="'aug-' + op.key"
              type="checkbox"
              class="form-check-input m-0"
              :checked="!!modelValue.ops[op.key]"
              @change="toggle(op, $event.target.checked)"
            />
            <label class="form-check-label mb-0" :for="'aug-' + op.key">
              <i class="fa me-1" :class="op.icon" />{{ $t('exportAugment.op.' + op.key) }}
            </label>
            <template v-if="op.param && modelValue.ops[op.key]">
              <select
                class="form-select form-select-sm w-auto ms-1 py-0"
                :value="modelValue.ops[op.key]"
                @change="setOp(op.key, Number($event.target.value))"
              >
                <option v-for="v in op.choices" :key="v" :value="v">{{ op.label(v) }}</option>
              </select>
            </template>
          </div>
          <div class="small text-muted hint">{{ $t('exportAugment.hint.' + op.key) }}</div>
        </div>
      </div>

      <div class="small mt-2" :class="chosen ? 'text-body' : 'text-danger'">
        <template v-if="!chosen">{{ $t('exportAugment.pickOne') }}</template>
        <template v-else-if="splitOn">
          {{ $t('exportAugment.summarySplit', { n: trainCount, copies: modelValue.copies, total: trainCount * modelValue.copies }) }}
        </template>
        <template v-else>
          {{ $t('exportAugment.summaryAll', { n: imageCount || 0, copies: modelValue.copies, total: (imageCount || 0) * modelValue.copies }) }}
        </template>
      </div>
      <div v-if="!splitOn" class="small text-warning-emphasis mt-1">
        <i class="fa fa-exclamation-triangle" /> {{ $t('exportAugment.noSplitWarning') }}
      </div>
      <div class="form-text mt-1">{{ $t('exportAugment.withImages') }}</div>
    </template>
  </div>
</template>

<script>
/** Options for augmenting the training images of an export. */
export const OPS = [
  { key: "hflip", icon: "fa-arrows-h" },
  { key: "vflip", icon: "fa-arrows-v" },
  { key: "rot90", icon: "fa-repeat" },
  { key: "rotate", icon: "fa-rotate-right", param: 15, choices: [5, 10, 15, 20, 30, 45], label: v => `±${v}°` },
  { key: "scale", icon: "fa-search-plus", param: 0.8, choices: [0.9, 0.8, 0.7, 0.6, 0.5], label: v => `${Math.round(v * 100)}%–100%` },
  { key: "color", icon: "fa-adjust" },
  { key: "blur", icon: "fa-tint" },
  { key: "noise", icon: "fa-braille" }
];

export function defaultAugment() {
  return { enabled: false, copies: 2, ops: { hflip: true, color: true } };
}

/** What the server gets (null when off or nothing chosen). */
export function augmentPayload(value) {
  if (!value || !value.enabled) return null;
  const ops = Object.fromEntries(Object.entries(value.ops).filter(([, v]) => v));
  return Object.keys(ops).length ? { copies: value.copies, ops } : null;
}

export default {
  name: "ExportAugment",
  props: {
    modelValue: { type: Object, required: true },
    imageCount: { type: Number, default: null },
    trainCount: { type: Number, default: 0 },
    splitOn: { type: Boolean, default: false }
  },
  emits: ["update:modelValue"],
  data() {
    return { OPS };
  },
  computed: {
    chosen() {
      return Object.values(this.modelValue.ops).some(Boolean);
    }
  },
  methods: {
    set(change) {
      this.$emit("update:modelValue", { ...this.modelValue, ...change });
    },
    setOp(key, value) {
      this.set({ ops: { ...this.modelValue.ops, [key]: value } });
    },
    toggle(op, on) {
      this.setOp(op.key, on ? op.param || true : false);
    }
  }
};
</script>

<style scoped>
.ops {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 8px 16px;
}
.op .hint {
  padding-left: 1.6rem;
  line-height: 1.3;
}
</style>
