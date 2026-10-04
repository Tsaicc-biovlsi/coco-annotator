<template>
  <div class="modal fade" tabindex="-1" role="dialog" :id="modalId">
    <div class="modal-dialog" role="document">
      <div class="modal-content text-start">
        <div class="modal-header">
          <h5 class="modal-title">
            {{ dataset ? $t('modelRun.titleDataset', { name: datasetName }) : $t('modelRun.titleImage') }}
          </h5>
          <button
            type="button"
            class="btn-close"
            data-bs-dismiss="modal"
            aria-label="Close"
          ></button>
        </div>

        <div class="modal-body">
          <div v-if="loading" class="text-muted">
            <i class="fa fa-spinner fa-spin" /> {{ $t('modelRun.loadingModels') }}
          </div>

          <div v-else-if="!installed" class="alert alert-warning mb-0">
            {{ $t('modelRun.notInstalled') }}
          </div>

          <div v-else-if="models.length === 0" class="alert alert-info mb-0">
            <i18n-t keypath="modelRun.noModels" tag="span">
              <template #folder><code>models/</code></template>
            </i18n-t>
          </div>

          <form v-else @submit.prevent="run">
            <div class="mb-3">
              <label class="form-label" :for="modalId + 'Model'">{{ $t('modelRun.model') }}</label>
              <select :id="modalId + 'Model'" v-model="options.model" class="form-select">
                <option v-for="m in models" :key="m.name" :value="m.name" :disabled="!!m.error">
                  {{ m.name }}{{ m.task ? ` (${taskLabel(m.task)})` : '' }}{{ m.error ? ` — ${$t('modelRun.cannotLoad')}` : '' }}
                </option>
              </select>
              <div v-if="selected && selected.classes" class="form-text">
                {{ $t('modelRun.classes', { n: selected.classes.length }) }}
                <span
                  v-for="c in selected.classes.slice(0, 30)"
                  :key="c"
                  class="badge me-1"
                  :class="hasCategory(c) ? 'text-bg-success' : 'text-bg-secondary'"
                >{{ c }}</span>
                <span v-if="selected.classes.length > 30">…</span>
                <div class="mt-1">{{ $t('modelRun.classesHint') }}</div>
              </div>
            </div>

            <div class="mb-3">
              <label class="form-label" :for="modalId + 'Conf'">
                {{ $t('modelRun.confidence') }}: <strong>{{ Number(options.conf).toFixed(2) }}</strong>
              </label>
              <input
                :id="modalId + 'Conf'"
                v-model.number="options.conf"
                type="range"
                class="form-range"
                min="0.05"
                max="0.95"
                step="0.05"
              />
              <div class="form-text">{{ $t('modelRun.confidenceHint') }}</div>
            </div>

            <div class="form-check">
              <input :id="modalId + 'Create'" v-model="options.createCategories" type="checkbox" class="form-check-input" />
              <label class="form-check-label" :for="modalId + 'Create'">{{ $t('modelRun.createCategories') }}</label>
            </div>

            <div v-if="dataset" class="form-check">
              <input :id="modalId + 'Skip'" v-model="options.skipAnnotated" type="checkbox" class="form-check-input" />
              <label class="form-check-label" :for="modalId + 'Skip'">{{ $t('modelRun.skipAnnotated') }}</label>
            </div>

            <div v-if="!dataset" class="form-text mt-2">{{ $t('modelRun.imageHint') }}</div>
            <div v-else class="form-text mt-2">{{ $t('modelRun.datasetHint') }}</div>
          </form>
        </div>

        <div class="modal-footer">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!canRun || running"
            @click="run"
          >
            <i v-if="running" class="fa fa-spinner fa-spin" />
            {{ $t('modelRun.run') }}
          </button>
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
            {{ $t('modelRun.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { showModal } from "@/libs/modal";

const STORAGE_KEY = "modelRunOptions";

function loadSaved() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || {};
  } catch {
    return {};
  }
}

export default {
  name: "ModelRunModal",
  props: {
    modalId: { type: String, required: true },
    // true: run over the whole dataset (background task); false: one image
    dataset: { type: Boolean, default: false },
    datasetName: { type: String, default: "" },
    // names of the categories the dataset already has
    categoryNames: { type: Array, default: () => [] },
    running: { type: Boolean, default: false }
  },
  emits: ["run"],
  data() {
    const saved = loadSaved();
    return {
      loading: false,
      installed: true,
      models: [],
      options: {
        model: saved.model || "",
        conf: saved.conf || 0.25,
        createCategories: saved.createCategories !== false,
        skipAnnotated: saved.skipAnnotated !== false
      }
    };
  },
  computed: {
    selected() {
      return this.models.find(m => m.name === this.options.model);
    },
    canRun() {
      return this.installed && this.selected && !this.selected.error;
    },
    lowerCategoryNames() {
      return this.categoryNames.map(n => n.toLowerCase());
    }
  },
  methods: {
    open() {
      showModal("#" + this.modalId);
      this.loadModels();
    },
    loadModels() {
      this.loading = true;
      axios
        .get("/api/model/yolo")
        .then(response => {
          this.installed = response.data.installed;
          this.models = response.data.models || [];
          if (!this.selected) {
            const usable = this.models.find(m => !m.error);
            this.options.model = usable ? usable.name : "";
          }
        })
        .finally(() => (this.loading = false));
    },
    hasCategory(name) {
      return this.lowerCategoryNames.includes(name.toLowerCase());
    },
    taskLabel(task) {
      const key = "modelRun.task." + task;
      return this.$te(key) ? this.$t(key) : task;
    },
    run() {
      if (!this.canRun || this.running) return;
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(this.options));
      } catch {
        // storage unavailable: the choice is just not remembered
      }
      this.$emit("run", {
        model: this.options.model,
        conf: this.options.conf,
        create_categories: this.options.createCategories,
        skip_annotated: this.options.skipAnnotated
      });
    }
  }
};
</script>
