<template>
  <div>
    <div style="padding-top: 55px" />
    <div class="bg-light trash-page" style="overflow: auto; height: calc(100vh - 55px)">
      <div class="container py-4">
        <!-- header -->
        <div class="d-flex align-items-start flex-wrap gap-2 mb-3">
          <div class="me-auto">
            <h3 class="mb-1"><i class="fa fa-trash-o" /> {{ $t('trash.title') }}</h3>
            <div class="text-muted small">
              {{ data && data.days ? $t('trash.keepDays', { days: data.days }) : $t('trash.keepForever') }}
            </div>
          </div>
          <button type="button" class="btn btn-sm btn-outline-secondary" :disabled="loading" @click="load">
            <i class="fa fa-refresh" :class="{ 'fa-spin': loading }" /> {{ $t('trash.refresh') }}
          </button>
          <button type="button" class="btn btn-sm btn-outline-danger" :disabled="!data || !data.all || busy" @click="emptyTrash">
            <i class="fa fa-trash" /> {{ $t('trash.empty') }}
          </button>
        </div>

        <!-- type tabs -->
        <ul class="nav nav-pills mb-3 flex-wrap">
          <li v-for="t in TYPES" :key="t" class="nav-item">
            <a href="#" class="nav-link py-1 px-3" :class="{ active: type === t }" @click.prevent="setType(t)">
              <i class="fa fa-fw" :class="ICONS[t]" />
              {{ $t('trash.type.' + t) }}
              <span class="badge rounded-pill ms-1" :class="type === t ? 'text-bg-light' : 'text-bg-secondary'">
                {{ t === 'all' ? (data ? data.all : 0) : (data ? data.counts[t] : 0) }}
              </span>
            </a>
          </li>
        </ul>

        <!-- filters -->
        <div class="row g-2 mb-3">
          <div class="col-md-4">
            <select v-model="filters.dataset_id" class="form-select form-select-sm">
              <option value="">{{ $t('trash.allDatasets') }}</option>
              <option v-for="d in (data ? data.datasets : [])" :key="d.id" :value="d.id">{{ d.name }}</option>
            </select>
          </div>
          <div class="col-md-3">
            <select v-model="filters.deleted_by" class="form-select form-select-sm">
              <option value="">{{ $t('trash.anyone') }}</option>
              <option v-for="u in (data ? data.deleters : [])" :key="u" :value="u">
                {{ u === '-' ? $t('trash.unknownDeleter') : u }}
              </option>
            </select>
          </div>
          <div class="col-md-5">
            <input v-model="search" class="form-control form-control-sm" :placeholder="$t('trash.search')" />
          </div>
        </div>

        <!-- bulk bar -->
        <div v-if="data && data.groups.length" class="d-flex align-items-center flex-wrap gap-2 mb-2 bulk-bar">
          <div class="form-check mb-0">
            <input id="trashAll" class="form-check-input" type="checkbox" :checked="allChecked" @change="toggleAll" />
            <label class="form-check-label small" for="trashAll">{{ $t('trash.selectPage') }}</label>
          </div>
          <span class="small text-muted">{{ $t('trash.selectedN', { n: selectedGroups.length }) }}</span>
          <button
            type="button"
            class="btn btn-sm btn-success ms-auto"
            :disabled="!selectedGroups.length || busy"
            @click="restoreGroups(selectedGroups)"
          >
            <i class="fa fa-undo" /> {{ $t('trash.restoreSelected') }}
          </button>
          <button
            type="button"
            class="btn btn-sm btn-danger"
            :disabled="!selectedGroups.length || busy"
            @click="purgeGroups(selectedGroups)"
          >
            <i class="fa fa-times" /> {{ $t('trash.purgeSelected') }}
          </button>
        </div>

        <div v-if="!data" class="text-muted"><i class="fa fa-spinner fa-spin" /></div>
        <div v-else-if="!data.groups.length" class="empty-state text-center text-muted py-5">
          <i class="fa fa-trash-o fa-3x mb-2 d-block" />
          {{ hasFilters ? $t('trash.noMatch') : $t('trash.isEmpty') }}
        </div>

        <!-- entries -->
        <div v-for="g in (data ? data.groups : [])" :key="g.key" class="card mb-2 shadow-sm trash-item" :class="{ checked: selected[g.key] }">
          <div class="card-body p-2 d-flex gap-3 align-items-start">
            <input v-model="selected[g.key]" class="form-check-input mt-1 flex-shrink-0" type="checkbox" />

            <div class="preview flex-shrink-0">
              <img
                v-if="previewUrl(g)"
                :src="previewUrl(g)"
                loading="lazy"
                alt=""
                @error="$event.target.style.visibility = 'hidden'"
              />
              <span v-else-if="g.type === 'category'" class="swatch" :style="{ backgroundColor: g.color || '#adb5bd' }" />
              <i v-else class="fa fa-3x" :class="ICONS[g.type]" />
            </div>

            <div class="flex-grow-1 min-w-0">
              <div class="d-flex align-items-center flex-wrap gap-2">
                <span class="badge text-bg-secondary"><i class="fa" :class="ICONS[g.type]" /> {{ $t('trash.type.' + g.type) }}</span>
                <strong class="text-break">{{ title(g) }}</strong>
              </div>

              <div v-if="g.type === 'annotation'" class="d-flex flex-wrap gap-1 mt-1">
                <span v-for="c in g.categories" :key="c.name" class="cat-chip">
                  <span class="dot" :style="{ backgroundColor: c.color || '#adb5bd' }" />{{ c.name }} × {{ c.n }}
                </span>
              </div>

              <div class="meta small text-muted mt-1">
                <span v-if="g.dataset && g.type !== 'dataset'"><i class="fa fa-database" /> {{ g.dataset.name }}</span>
                <span><i class="fa fa-user-o" /> {{ g.deleted_by || $t('trash.unknownDeleter') }}</span>
                <span :title="g.deleted_at"><i class="fa fa-clock-o" /> {{ when(g.deleted_at) }}</span>
                <span v-if="g.expires_at" :class="{ 'text-danger': daysLeft(g) <= 7 }">
                  {{ $t('trash.daysLeft', { n: daysLeft(g) }) }}
                </span>
              </div>

              <div v-if="parentNote(g)" class="small text-warning-emphasis mt-1">
                <i class="fa fa-info-circle" /> {{ parentNote(g) }}
              </div>

              <!-- details of a multi-annotation entry -->
              <template v-if="g.type === 'annotation' && g.count > 1">
                <a href="#" class="small" @click.prevent="toggleOpen(g.key)">
                  {{ open[g.key] ? $t('trash.hideItems') : $t('trash.showItems', { n: g.count }) }}
                </a>
                <div v-if="open[g.key]" class="d-flex flex-wrap gap-2 mt-2">
                  <div v-for="item in g.items" :key="item.id" class="mini">
                    <img
                      v-if="g.image"
                      :src="previewSrc(g.image.id, [item.id], 96, true)"
                      loading="lazy"
                      alt=""
                      @error="$event.target.style.visibility = 'hidden'"
                    />
                    <div class="small text-truncate">
                      <span class="dot" :style="{ backgroundColor: item.color || '#adb5bd' }" />{{ item.category }}
                    </div>
                    <div class="d-flex gap-1">
                      <button
                        type="button"
                        class="btn btn-sm btn-outline-success py-0 px-1"
                        :title="$t('trash.restore')"
                        :disabled="busy"
                        @click="restoreItems([{ type: 'annotation', ids: [item.id] }])"
                      ><i class="fa fa-undo" /></button>
                      <button
                        type="button"
                        class="btn btn-sm btn-outline-danger py-0 px-1"
                        :title="$t('trash.purge')"
                        :disabled="busy"
                        @click="purgeItems([{ type: 'annotation', ids: [item.id] }], 1, false)"
                      ><i class="fa fa-times" /></button>
                    </div>
                  </div>
                </div>
              </template>
            </div>

            <div class="d-flex flex-column gap-1 flex-shrink-0">
              <button type="button" class="btn btn-sm btn-outline-success" :disabled="busy" @click="restoreGroups([g])">
                <i class="fa fa-undo" /> {{ $t('trash.restore') }}
              </button>
              <button type="button" class="btn btn-sm btn-outline-danger" :disabled="busy" @click="purgeGroups([g])">
                <i class="fa fa-times" /> {{ $t('trash.purge') }}
              </button>
            </div>
          </div>
        </div>

        <div v-if="data && data.pages > 1" class="d-flex justify-content-center mt-3">
          <Pagination :pages="data.pages" @pagechange="p => load(p)" />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import Pagination from "@/components/Pagination.vue";

const TYPES = ["all", "annotation", "image", "category", "dataset"];
const ICONS = {
  all: "fa-th-list",
  annotation: "fa-object-group",
  image: "fa-picture-o",
  category: "fa-tag",
  dataset: "fa-database"
};

export default {
  name: "Trash",
  components: { Pagination },
  data() {
    return {
      TYPES,
      ICONS,
      data: null,
      type: "all",
      page: 1,
      filters: { dataset_id: "", deleted_by: "" },
      search: "",
      searchTimer: null,
      selected: {},
      open: {},
      loading: false,
      busy: false
    };
  },
  computed: {
    selectedGroups() {
      return (this.data ? this.data.groups : []).filter(g => this.selected[g.key]);
    },
    allChecked() {
      return !!this.data && this.data.groups.length > 0 && this.data.groups.every(g => this.selected[g.key]);
    },
    hasFilters() {
      return this.type !== "all" || this.filters.dataset_id !== "" || this.filters.deleted_by !== "" || !!this.search.trim();
    }
  },
  watch: {
    filters: {
      deep: true,
      handler() {
        this.load(1);
      }
    },
    search() {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => this.load(1), 300);
    }
  },
  created() {
    this.load(1);
  },
  methods: {
    load(page = this.page) {
      this.page = page;
      this.loading = true;
      const params = { type: this.type, page, per_page: 20, q: this.search.trim() };
      if (this.filters.dataset_id !== "") params.dataset_id = this.filters.dataset_id;
      if (this.filters.deleted_by) params.deleted_by = this.filters.deleted_by;
      return axios
        .get("/api/trash/", { params })
        .then(r => {
          this.data = r.data;
          this.selected = {};
        })
        .finally(() => (this.loading = false));
    },
    setType(t) {
      this.type = t;
      this.load(1);
    },
    toggleAll(event) {
      const next = {};
      if (event.target.checked) this.data.groups.forEach(g => (next[g.key] = true));
      this.selected = next;
    },
    toggleOpen(key) {
      this.open = { ...this.open, [key]: !this.open[key] };
    },
    title(g) {
      if (g.type === "annotation") {
        return this.$t("trash.annotationTitle", { n: g.count, file: g.image ? g.image.file_name : "?" });
      }
      if (g.type === "dataset") return this.$t("trash.datasetTitle", { name: g.title, n: g.images || 0 });
      return g.title || "-";
    },
    previewSrc(imageId, annotationIds, size, crop) {
      const params = new URLSearchParams({ image_id: imageId, size });
      if (annotationIds && annotationIds.length) params.set("annotations", annotationIds.slice(0, 200).join(","));
      if (crop) params.set("crop", "1");
      return `/api/trash/preview?${params}`;
    },
    previewUrl(g) {
      if (!g.image) return null;
      if (g.type === "annotation") return this.previewSrc(g.image.id, g.ids, 192, g.count === 1);
      if (g.type === "image") return this.previewSrc(g.image.id, [], 192, false);
      return null;
    },
    when(iso) {
      if (!iso) return "-";
      const date = new Date(iso);
      const pad = n => String(n).padStart(2, "0");
      const text = `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
      const minutes = Math.max(0, Math.round((Date.now() - date) / 60000));
      let ago;
      if (minutes < 1) ago = this.$t("trash.justNow");
      else if (minutes < 60) ago = this.$t("trash.minutesAgo", { n: minutes });
      else if (minutes < 60 * 24) ago = this.$t("trash.hoursAgo", { n: Math.round(minutes / 60) });
      else ago = this.$t("trash.daysAgo", { n: Math.round(minutes / 1440) });
      return `${text}（${ago}）`;
    },
    daysLeft(g) {
      return Math.max(0, Math.ceil((new Date(g.expires_at) - Date.now()) / 86400000));
    },
    parentNote(g) {
      if (g.type === "annotation" && g.image && g.image.deleted) return this.$t("trash.parentImage");
      if ((g.type === "annotation" || g.type === "image") && g.dataset && g.dataset.deleted) return this.$t("trash.parentDataset");
      return "";
    },
    itemsOf(groups) {
      const byType = {};
      groups.forEach(g => (byType[g.type] = [...(byType[g.type] || []), ...g.ids]));
      return Object.entries(byType).map(([type, ids]) => ({ type, ids }));
    },
    count(groups) {
      return groups.reduce((n, g) => n + g.count, 0);
    },
    restoreGroups(groups) {
      return this.restoreItems(this.itemsOf(groups));
    },
    async restoreItems(items, includeParents = false) {
      this.busy = true;
      try {
        const r = await axios.post("/api/trash/restore", { items, include_parents: includeParents });
        this.$toastr.success(this.$t("trash.restored", { n: r.data.restored }));
        await this.load();
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        if (error.response && error.response.status === 409 && !includeParents) {
          const parents = data.parents || {};
          const what = [
            parents.image ? this.$t("trash.nImages", { n: parents.image.length }) : null,
            parents.dataset ? this.$t("trash.nDatasets", { n: parents.dataset.length }) : null
          ].filter(Boolean).join("、");
          if (confirm(this.$t("trash.confirmParents", { what }))) {
            this.busy = false;
            return this.restoreItems(items, true);
          }
        } else {
          this.$toastr.error(data.message || String(error));
        }
      } finally {
        this.busy = false;
      }
    },
    purgeGroups(groups) {
      const files = groups.some(g => g.type === "image" || g.type === "dataset");
      return this.purgeItems(this.itemsOf(groups), this.count(groups), files);
    },
    async purgeItems(items, n, files) {
      const message = this.$t("trash.confirmPurge", { n }) + (files ? "\n\n" + this.$t("trash.filesToo") : "");
      if (!confirm(message)) return;
      this.busy = true;
      try {
        const r = await axios.post("/api/trash/purge", { items });
        this.$toastr.success(this.$t("trash.purged", { n: r.data.deleted }));
        await this.load();
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      } finally {
        this.busy = false;
      }
    },
    async emptyTrash() {
      if (!confirm(this.$t("trash.confirmEmpty", { n: this.data.all }) + "\n\n" + this.$t("trash.filesToo"))) return;
      this.busy = true;
      try {
        const r = await axios.post("/api/trash/empty");
        this.$toastr.success(this.$t("trash.purged", { n: r.data.deleted }));
        await this.load(1);
      } finally {
        this.busy = false;
      }
    }
  }
};
</script>

<style scoped>
.trash-page {
  text-align: left;
}
.trash-item.checked {
  outline: 2px solid #0d6efd;
}
.preview {
  width: 96px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f3f5;
  border-radius: 6px;
  overflow: hidden;
  color: #adb5bd;
}
.preview img {
  max-width: 100%;
  max-height: 100%;
}
.preview .swatch {
  width: 40px;
  height: 40px;
  border-radius: 50%;
}
.min-w-0 {
  min-width: 0;
}
.meta span + span::before {
  content: "·";
  margin: 0 6px;
}
.cat-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border: 1px solid #dee2e6;
  border-radius: 999px;
  padding: 0 8px;
  font-size: 0.75rem;
  background: #fff;
}
.dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  margin-right: 3px;
}
.mini {
  width: 104px;
  border: 1px solid #e9ecef;
  border-radius: 6px;
  padding: 4px;
  background: #fff;
}
.mini img {
  width: 96px;
  height: 64px;
  object-fit: contain;
  background: #f1f3f5;
  border-radius: 4px;
}
.bulk-bar {
  position: sticky;
  top: 0;
  z-index: 2;
  background: #f8f9fa;
  padding: 4px 0;
}
</style>
