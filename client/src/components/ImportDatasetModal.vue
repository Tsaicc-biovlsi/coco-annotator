<template>
  <div class="modal fade" tabindex="-1" role="dialog" id="importDataset">
    <div class="modal-dialog" role="document">
      <div class="modal-content text-start">
        <div class="modal-header">
          <h5 class="modal-title">{{ $t('importDataset.title') }}</h5>
          <button
            type="button"
            class="btn-close"
            data-bs-dismiss="modal"
            aria-label="Close"
            :disabled="running"
          ></button>
        </div>

        <div class="modal-body">
          <form @submit.prevent="run">
            <div class="mb-3">
              <label class="form-label" for="importTarget">{{ $t('importDataset.dataset') }}</label>
              <select id="importTarget" v-model="target" class="form-select" :disabled="running">
                <option value="new">{{ $t('importDataset.newDataset') }}</option>
                <option v-for="d in datasets" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
              <input
                v-if="target === 'new'"
                v-model="newName"
                class="form-control mt-2"
                :placeholder="$t('importDataset.newName')"
                :disabled="running"
              />
            </div>

            <div class="mb-3">
              <label class="form-label">{{ $t('importDataset.images') }}</label>
              <div class="d-flex gap-2 flex-wrap">
                <button type="button" class="btn btn-outline-primary btn-sm" :disabled="running" @click="$refs.files.click()">
                  <i class="fa fa-file-image-o" /> {{ $t('importDataset.chooseImages') }}
                </button>
                <button type="button" class="btn btn-outline-primary btn-sm" :disabled="running" @click="$refs.folder.click()">
                  <i class="fa fa-folder-open-o" /> {{ $t('importDataset.chooseFolder') }}
                </button>
                <button v-if="images.length" type="button" class="btn btn-link btn-sm" :disabled="running" @click="images = []">
                  {{ $t('importDataset.clear') }}
                </button>
              </div>
              <input ref="files" type="file" multiple :accept="imageAccept" class="d-none" @change="addImages" />
              <input ref="folder" type="file" webkitdirectory directory multiple class="d-none" @change="addImages" />
              <div class="form-text">
                <span v-if="images.length">{{ $t('importDataset.selected', { n: images.length, size: totalSize }) }}</span>
                <span v-else>{{ $t('importDataset.imagesHint') }}</span>
              </div>
            </div>

            <div class="mb-3">
              <label class="form-label" for="importCoco">{{ $t('importDataset.coco') }}</label>
              <input
                id="importCoco"
                ref="coco"
                type="file"
                accept=".json,application/json"
                class="form-control"
                :disabled="running"
                @change="coco = $event.target.files[0] || null"
              />
              <div class="form-text">{{ $t('importDataset.cocoHint') }}</div>
            </div>

            <div v-if="running || progress.total" class="mb-2">
              <div class="progress" style="height: 20px">
                <div class="progress-bar" :style="{ width: percent + '%' }">
                  {{ progress.done }} / {{ progress.total }}
                </div>
              </div>
              <div class="form-text">
                {{ $t('importDataset.progress', { skipped: progress.skipped, failed: progress.failed.length }) }}
              </div>
            </div>
          </form>
        </div>

        <div class="modal-footer">
          <button type="button" class="btn btn-primary" :disabled="!canRun || running" @click="run">
            <i v-if="running" class="fa fa-spinner fa-spin" />
            {{ $t('importDataset.import') }}
          </button>
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal" :disabled="running">
            {{ $t('importDataset.close') }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { showModal, hideModal } from "@/libs/modal";

const IMAGE_EXT = [".gif", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff"];
const PARALLEL_UPLOADS = 4;

function isImage(file) {
  const name = file.name.toLowerCase();
  return !name.startsWith(".") && IMAGE_EXT.some(ext => name.endsWith(ext));
}

export default {
  name: "ImportDatasetModal",
  emits: ["done"],
  data() {
    return {
      datasets: [],
      target: "new",
      newName: "",
      images: [],
      coco: null,
      running: false,
      progress: { done: 0, total: 0, skipped: 0, failed: [] },
      imageAccept: IMAGE_EXT.join(",")
    };
  },
  computed: {
    canRun() {
      const hasTarget = this.target !== "new" || this.newName.trim().length > 0;
      return hasTarget && (this.images.length > 0 || this.coco || this.target === "new");
    },
    percent() {
      return this.progress.total ? Math.round((100 * this.progress.done) / this.progress.total) : 0;
    },
    totalSize() {
      const mb = this.images.reduce((n, f) => n + f.size, 0) / 1024 / 1024;
      return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb.toFixed(1)} MB`;
    }
  },
  methods: {
    open(datasetId) {
      this.target = datasetId || "new";
      this.newName = "";
      this.images = [];
      this.coco = null;
      this.progress = { done: 0, total: 0, skipped: 0, failed: [] };
      if (this.$refs.coco) this.$refs.coco.value = "";
      showModal("#importDataset");
      axios.get("/api/dataset/").then(r => {
        this.datasets = (r.data || []).sort((a, b) => a.name.localeCompare(b.name));
      });
    },
    addImages(event) {
      const seen = new Set(this.images.map(f => f.name));
      for (const file of event.target.files) {
        // a folder pick includes everything: keep the images, once per name
        if (isImage(file) && !seen.has(file.name)) {
          seen.add(file.name);
          this.images.push(file);
        }
      }
      event.target.value = "";
    },
    async createDataset() {
      const response = await axios.post("/api/dataset/", { name: this.newName.trim() });
      return response.data.id;
    },
    async uploadAll(datasetId) {
      const queue = [...this.images];
      this.progress = { done: 0, total: queue.length, skipped: 0, failed: [] };
      const worker = async () => {
        while (queue.length) {
          const file = queue.shift();
          const form = new FormData();
          form.append("image", file);
          form.append("dataset_id", datasetId);
          try {
            const r = await axios.post("/api/image/", form, {
              headers: { "Content-Type": "multipart/form-data" }
            });
            if (r.data.existed) this.progress.skipped += 1;
          } catch {
            this.progress.failed.push(file.name);
          }
          this.progress.done += 1;
        }
      };
      await Promise.all(Array.from({ length: PARALLEL_UPLOADS }, worker));
    },
    async run() {
      if (!this.canRun || this.running) return;
      this.running = true;
      let datasetId = this.target;
      try {
        if (this.target === "new") datasetId = await this.createDataset();
        if (this.images.length) await this.uploadAll(datasetId);

        let importTask = null;
        if (this.coco) {
          const form = new FormData();
          form.append("coco", this.coco);
          const r = await axios.post(`/api/dataset/${datasetId}/coco`, form, {
            headers: { "Content-Type": "multipart/form-data" }
          });
          importTask = r.data.id;
        }

        const p = this.progress;
        const uploaded = p.total - p.skipped - p.failed.length;
        this.$toastr.success(this.$t("importDataset.done", { uploaded, skipped: p.skipped }));
        if (p.failed.length) {
          this.$toastr.warning(
            this.$t("importDataset.failed", { n: p.failed.length, names: p.failed.slice(0, 5).join(", ") })
          );
        }
        hideModal("#importDataset");
        this.$emit("done", { datasetId, importTask });
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error), this.$t("importDataset.title"));
      } finally {
        this.running = false;
      }
    }
  }
};
</script>
