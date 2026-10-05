<template>
  <div class="image-class">
    <div class="d-flex align-items-center mb-1">
      <span class="title me-auto">{{ $t('imageClass.title') }}</span>
      <span v-if="saving" class="small"><i class="fa fa-spinner fa-spin" /></span>
    </div>
    <div class="d-flex flex-wrap gap-1">
      <button
        v-for="category in categories"
        :key="category.id"
        type="button"
        class="btn btn-sm class-pill"
        :class="{ selected: value === category.id }"
        :style="pillStyle(category)"
        :disabled="!canEdit || saving"
        :title="value === category.id ? $t('imageClass.clear') : $t('imageClass.set', { name: category.name })"
        @click="choose(category.id)"
      >
        <i v-if="value === category.id" class="fa fa-check" /> {{ category.name }}
      </button>
      <span v-if="!categories.length" class="small hint">{{ $t('imageClass.noCategories') }}</span>
    </div>
    <div class="form-check form-switch mt-1 small">
      <input id="imageClassNext" v-model="autoNext" class="form-check-input" type="checkbox" />
      <label class="form-check-label hint" for="imageClassNext">{{ $t('imageClass.autoNext') }}</label>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { textColorFor } from "@/libs/colors";

const AUTO_NEXT_KEY = "imageClass/autoNext";

export default {
  name: "ImageClassPicker",
  props: {
    imageId: { type: Number, required: true },
    value: { type: Number, default: null },
    categories: { type: Array, default: () => [] },
    canEdit: { type: Boolean, default: false },
    nextImageId: { type: Number, default: null }
  },
  emits: ["update:value", "navigate"],
  data() {
    let autoNext = false;
    try {
      autoNext = localStorage.getItem(AUTO_NEXT_KEY) === "true";
    } catch {
      // storage unavailable
    }
    return { saving: false, autoNext };
  },
  watch: {
    autoNext(value) {
      try {
        localStorage.setItem(AUTO_NEXT_KEY, String(value));
      } catch {
        // ignore
      }
    }
  },
  methods: {
    pillStyle(category) {
      const color = category.color || "#6c757d";
      return this.value === category.id
        ? { backgroundColor: color, borderColor: color, color: textColorFor(color) }
        : { borderColor: color, color: "#e9ecef" };
    },
    async choose(id) {
      const next = this.value === id ? null : id;
      this.saving = true;
      try {
        await axios.post(`/api/image/${this.imageId}/class`, { category_id: next });
        this.$emit("update:value", next);
        if (next != null && this.autoNext && this.nextImageId) this.$emit("navigate", this.nextImageId);
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      } finally {
        this.saving = false;
      }
    }
  }
};
</script>

<style scoped>
.image-class {
  padding: 4px 10px 6px;
  color: #e9ecef;
  font-size: 13px;
}
.title {
  font-weight: 600;
}
.hint {
  color: #ced4da;
}
.class-pill {
  border: 1px solid;
  background: transparent;
  padding: 1px 8px;
  font-size: 12px;
}
.class-pill.selected {
  font-weight: 600;
}
</style>
