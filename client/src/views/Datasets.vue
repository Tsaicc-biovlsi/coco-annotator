<template>
  <div>
    <div style="padding-top: 55px" />

    <div
      class="album py-5 bg-light"
      style="overflow: auto; height: calc(100vh - 55px)"
    >
      <div class="page-container">
        <h2 class="text-center">
          {{ $t('datasets.datasets') }}
          <i
            class="fa fa-question-circle help-icon"
            data-bs-toggle="modal"
            data-bs-target="#helpDataset"
            aria-hidden="true"
          />
        </h2>

        <p class="text-center">
          <i18n-t keypath="datasets.loaded" tag="span"><template #n><strong>{{ datasets.length }}</strong></template></i18n-t>
        </p>

        <div class="row justify-content-md-center">
          <div
            class="col-md-auto btn-group"
            role="group"
            style="padding-bottom: 20px"
          >
            <button
              type="button"
              class="btn btn-success"
              @click="openCreate"
            >
              {{ $t('datasets.create') }}
            </button>
            <button type="button" class="btn btn-primary" @click="$refs.importModal.open()">
              {{ $t('datasets.import') }}
            </button>
            <button type="button" class="btn btn-info text-white" @click="openExportPick">
              {{ $t('datasets.export') }}
            </button>
            <button
              type=" button"
              class="btn btn-secondary"
              @click="updatePage(page)"
            >
              {{ $t('datasets.refresh') }}
            </button>
          </div>
        </div>

        <hr />
        <p v-if="loaded && total < 1 && !search" class="text-center">
          {{ $t('datasets.youNeedToCreateA') }}
        </p>
        <div v-else-if="loaded">
          <!-- one tab per parent category used by the datasets' categories -->
          <ul v-if="parents.length" class="nav nav-tabs mb-3 parent-tabs">
            <li v-for="t in tabs" :key="t.key" class="nav-item">
              <a href="#" class="nav-link" :class="{ active: t.key === activeTop }" @click.prevent="selectTab(t.key)">
                <i class="fa" :class="t.icon" />
                {{ t.label }}
                <span class="badge rounded-pill text-bg-secondary ms-1">{{ t.count }}</span>
              </a>
            </li>
          </ul>

          <!-- deeper levels (a › b › ...): where we are, and the folders inside -->
          <div v-if="subPath.length > 1 || subChildren.length" class="sub-levels d-flex flex-wrap align-items-center gap-1 mb-3">
            <template v-for="(a, i) in subPath" :key="a">
              <i v-if="i > 0" class="fa fa-angle-right text-muted" />
              <a v-if="i < subPath.length - 1" href="#" class="small" @click.prevent="selectTab(a)">{{ pathName(a) }}</a>
              <strong v-else class="small">{{ pathName(a) }}</strong>
            </template>
            <span v-if="subChildren.length" class="mx-1 text-muted">|</span>
            <button
              v-for="c in subChildren"
              :key="c.name"
              type="button"
              class="btn btn-sm sub-chip btn-outline-secondary"
              @click="selectTab(c.name)"
            >
              <i class="fa fa-folder-o" /> {{ pathName(c.name) }} <span class="opacity-75">{{ c.count }}</span>
            </button>
          </div>

          <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
            <input
              v-model="search"
              class="form-control form-control-sm search-box"
              :placeholder="$t('datasets.searchName')"
            />
            <span v-if="shownTotal" class="small text-muted ms-auto">
              {{ $t('parents.showing', { from: (page - 1) * limit + 1, to: Math.min(page * limit, shownTotal), n: shownTotal }) }}
            </span>
          </div>

          <div class="row">
            <DatasetCard
              v-for="dataset in datasets"
              :key="dataset.id"
              :dataset="dataset"
              :categories="categories"
            />
          </div>
          <p v-if="!datasets.length" class="text-center text-muted">{{ $t('exportCategories.noMatch') }}</p>
          <div v-if="pages > 1" class="d-flex justify-content-center">
            <Pagination :key="parent + '|' + search + '|' + pages" :pages="pages" @pagechange="updatePage" />
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="createDataset">
      <div class="modal-dialog modal-lg" role="document">
        <div class="modal-content text-start">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('datasets.creatingADataset') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body pt-2">
            <WizardSteps
              :labels="createStepLabels"
              :current="create.step"
              :can-go="canGoCreateStep"
              @go="step => (create.step = step)"
            />
            <form @submit.prevent>
              <!-- 1: name -->
              <div v-show="create.step === 1">
                <div class="mb-3" :class="{ 'was-validated': create.touched && validDatasetName.length !== 0 }">
                  <label class="form-label" for="createName">{{ $t('datasets.datasetName2') }}</label>
                  <input
                    id="createName"
                    ref="createName"
                    v-model="create.name"
                    class="form-control"
                    :placeholder="$t('datasets.datasetName')"
                    required
                    @input="create.touched = true"
                    @keydown.enter.prevent="nextCreateStep"
                  />
                  <div class="invalid-feedback">{{ validDatasetName }}</div>
                </div>
                <!-- the same name is in the trash: bring it back, or start again in its folder -->
                <div v-if="trashedSameName" class="alert alert-warning py-2 small">
                  <div class="mb-2">
                    <i class="fa fa-trash-o" />
                    {{ $t('datasets.inTrash', { name: trashedSameName.name, n: trashedSameName.images }) }}
                  </div>
                  <div class="d-flex flex-wrap gap-2">
                    <button type="button" class="btn btn-sm btn-success" :disabled="creating" @click="restoreTrashed">
                      <i class="fa fa-undo" /> {{ $t('datasets.restoreOld') }}
                    </button>
                    <button
                      type="button"
                      class="btn btn-sm"
                      :class="create.replaceTrashed ? 'btn-primary' : 'btn-outline-primary'"
                      @click="create.replaceTrashed = !create.replaceTrashed"
                    >
                      <i class="fa" :class="create.replaceTrashed ? 'fa-check-square-o' : 'fa-square-o'" />
                      {{ $t('datasets.replaceOld') }}
                    </button>
                  </div>
                  <div class="mt-1 text-muted">{{ $t('datasets.replaceOldHint') }}</div>
                </div>
                <div class="mb-1">
                  <label class="form-label">{{ $t('datasets.folderDirectory') }}</label>
                  <input class="form-control" disabled :value="directory" />
                </div>
              </div>

              <!-- 2: planned task -->
              <div v-show="create.step === 2">
                <TaskPicker v-model="create.task" name="createTask" />
                <div class="form-text">{{ $t('datasetTask.hint') }}</div>
              </div>

              <!-- 3: categories -->
              <div v-show="create.step === 3">
                <CategoryPicker ref="categoryPicker" v-model="create.categories" :categories="categories" />
              </div>

              <!-- 4: review -->
              <div v-show="create.step === 4">
                <dl class="row create-review mb-0">
                  <dt class="col-4">{{ $t('datasets.datasetName2') }}</dt>
                  <dd class="col-8">
                    {{ create.name }}
                    <a href="#" class="ms-1 small" @click.prevent="create.step = 1">{{ $t('exportSteps.edit') }}</a>
                    <div class="small text-muted">{{ directory }}</div>
                    <div v-if="trashedSameName && create.replaceTrashed" class="small text-warning-emphasis">
                      <i class="fa fa-exclamation-triangle" /> {{ $t('datasets.replaceOldReview', { n: trashedSameName.images }) }}
                    </div>
                  </dd>
                  <dt class="col-4">{{ $t('datasetTask.label') }}</dt>
                  <dd class="col-8">
                    {{ $t('datasetTask.' + (create.task || 'none') + '.name') }}
                    <a href="#" class="ms-1 small" @click.prevent="create.step = 2">{{ $t('exportSteps.edit') }}</a>
                  </dd>
                  <dt class="col-4">{{ $t('datasets.defaultCategories') }}</dt>
                  <dd class="col-8 mb-0">
                    <template v-if="create.categories.length">
                      <span v-for="(key, i) in create.categories" :key="key" class="badge text-bg-light border me-1">
                        {{ i }}. {{ $refs.categoryPicker ? $refs.categoryPicker.labelOf(key) : key }}
                      </span>
                    </template>
                    <span v-else class="text-muted">{{ $t('datasets.noCategoriesYet') }}</span>
                    <a href="#" class="ms-1 small" @click.prevent="create.step = 3">{{ $t('exportSteps.edit') }}</a>
                  </dd>
                </dl>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              v-if="create.step > 1"
              type="button"
              class="btn btn-outline-secondary me-auto"
              @click="create.step -= 1"
            >
              <i class="fa fa-chevron-left" /> {{ $t('exportSteps.back') }}
            </button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">
              {{ $t('datasets.close') }}
            </button>
            <button
              v-if="create.step < 4"
              type="button"
              class="btn btn-primary"
              :disabled="!canGoCreateStep(create.step + 1)"
              @click="nextCreateStep"
            >
              {{ $t('exportSteps.next') }} <i class="fa fa-chevron-right" />
            </button>
            <button
              v-else
              type="button"
              class="btn btn-success"
              :disabled="creating || !canGoCreateStep(4)"
              @click="createDataset"
            >
              <i class="fa" :class="creating ? 'fa-spinner fa-spin' : 'fa-plus'" /> {{ $t('datasets.createDataset') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="helpDataset">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('datasets.datasets') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>

          <div class="modal-body">
            {{ $t('datasets.moreInformationCanBeFound') }}
            <a href="/help">{{ $t('datasets.helpSection') }}</a>.
            <hr />
            <h6>{{ $t('datasets.whatIsADataset') }}</h6>
            {{ $t('datasets.aDatasetIsACollection') }}
            <hr />
            <h6>{{ $t('datasets.howDoICreateOne') }}</h6>
            {{ $t('datasets.clickOnTheCreateButton') }}
            <hr />
            <h6>{{ $t('datasets.howDoIAddImages') }}</h6>
            {{ $t('datasets.onceYouHaveCreatedA') }}
          </div>

          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('datasets.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <ImportDatasetModal ref="importModal" @done="onImported" />

    <!-- which datasets go into one export (then the dataset's export wizard) -->
    <div class="modal fade" tabindex="-1" role="dialog" id="exportPick">
      <div class="modal-dialog" role="document">
        <div class="modal-content text-start">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('exportPick.title') }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" :aria-label="$t('datasets.close')" />
          </div>
          <div class="modal-body">
            <div class="small text-muted mb-2">{{ $t('exportPick.hint') }}</div>
            <input
              v-if="exportPick.list.length > 6"
              v-model="exportPick.filter"
              class="form-control form-control-sm mb-2"
              :placeholder="$t('exportMerge.search')"
            />
            <div v-if="exportPick.loading" class="text-muted small"><i class="fa fa-spinner fa-spin" /></div>
            <div v-else-if="!exportPick.list.length" class="text-muted small">{{ $t('exportPick.none') }}</div>
            <div v-else class="pick-list">
              <label v-for="d in shownExportPick" :key="d.id" class="pick-item">
                <input v-model="exportPick.chosen" type="checkbox" class="form-check-input m-0" :value="d.id" />
                <span class="text-truncate flex-grow-1">
                  <span v-if="exportPick.chosen[0] === d.id" class="badge text-bg-secondary me-1" :title="$t('exportPick.mainHint')">{{ $t('exportPick.main') }}</span>
                  {{ d.name }}
                </span>
                <span class="small text-muted text-nowrap">{{ $t('exportMerge.images', { n: d.images }) }}</span>
                <span v-if="pickMismatch(d)" class="small text-warning-emphasis text-nowrap" :title="pickMismatch(d)">
                  <i class="fa fa-exclamation-triangle" /> {{ $t('exportMerge.differs') }}
                </span>
              </label>
            </div>
            <div v-if="exportPick.chosen.length > 1" class="small mt-2">
              {{ $t('exportPick.summary', { n: exportPick.chosen.length, images: exportPickImages }) }}
            </div>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ $t('datasets.close') }}</button>
            <button type="button" class="btn btn-primary" :disabled="!exportPick.chosen.length" @click="goExport">
              {{ $t('exportPick.next') }} <i class="fa fa-chevron-right" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import toastrs from "@/mixins/toastrs";
import Datasets from "@/models/datasets";
import AdminPanel from "@/models/admin";
import DatasetCard from "@/components/cards/DatasetCard.vue";
import Pagination from "@/components/Pagination.vue";
import ImportDatasetModal from "@/components/ImportDatasetModal.vue";
import TaskPicker from "@/components/TaskPicker.vue";
import CategoryPicker from "@/components/CategoryPicker.vue";
import { ancestors, byName, pathName } from "@/libs/parents";
import WizardSteps from "@/components/WizardSteps.vue";
import { showModal, hideModal } from "@/libs/modal";

import { mapMutations } from "vuex";

function readTab() {
  try {
    return localStorage.getItem("datasets.tab") || "";
  } catch {
    return "";
  }
}

export default {
  name: "Datasets",
  components: { DatasetCard, Pagination, ImportDatasetModal, TaskPicker, CategoryPicker, WizardSteps },
  mixins: [toastrs],
  data() {
    return {
      exportPick: { list: [], chosen: [], filter: "", loading: false },
      pages: 1,
      limit: 12,
      page: 1,
      loaded: false,
      parent: readTab(),
      search: "",
      searchTimer: null,
      parents: [],
      noParent: 0,
      total: 0,
      shownTotal: 0,
      allNames: [],
      trashed: [],
      create: {
        step: 1,
        touched: false,
        name: "",
        categories: [],
        task: ""
      },
      creating: false,
      datasets: [],
      subdirectories: [],
      categories: [],
      users: []
    };
  },
  methods: {
    pathName,
    ...mapMutations(["addProcess", "removeProcess"]),
    selectTab(key) {
      this.parent = key;
      try {
        localStorage.setItem("datasets.tab", key);
      } catch {
        // not remembered
      }
      this.updatePage(1);
    },
    updatePage(page) {
      let process = "Loading datasets";
      this.addProcess(process);

      page = page || this.page;
      this.page = page;

      Datasets.allData({
        limit: this.limit,
        page: page,
        parent: this.parent,
        q: this.search.trim()
      }).then(response => {
        this.loaded = true;
        this.parents = response.data.parents || [];
        this.noParent = response.data.no_parent || 0;
        this.total = response.data.total || 0;
        this.shownTotal = response.data.pagination.total;
        this.allNames = response.data.names || [];
        this.trashed = response.data.trashed || [];
        // a remembered tab that no longer exists: back to all
        if (this.parent && this.parent !== "-" && !this.parents.some(p => p.name === this.parent)) {
          this.selectTab("");
          return;
        }
        this.datasets = response.data.datasets;
        this.categories = response.data.categories;
        this.subdirectories = response.data.subdirectories;
        this.pages = response.data.pagination.pages;
        this.page = response.data.pagination.page;
        AdminPanel.getUsers(this.limit)
          .then(response => {
            this.users = response.data.users;
          });
      })
      .finally(() => this.removeProcess(process));
    },
    openExportPick() {
      this.exportPick.loading = true;
      this.exportPick.filter = "";
      showModal("#exportPick");
      axios
        .get("/api/dataset/exportable")
        .then(r => {
          this.exportPick.list = r.data.datasets || [];
          const ids = this.exportPick.list.map(d => d.id);
          this.exportPick.chosen = this.exportPick.chosen.filter(id => ids.includes(id));
        })
        .catch(() => (this.exportPick.list = []))
        .finally(() => (this.exportPick.loading = false));
    },
    /** categories that differ from the first ticked dataset */
    pickMismatch(d) {
      const first = this.exportPick.list.find(x => x.id === this.exportPick.chosen[0]);
      if (!first || first.id === d.id || !this.exportPick.chosen.includes(d.id)) return "";
      const key = c => c.name.trim().toLowerCase();
      const mine = new Set(first.categories.map(key));
      const theirs = new Set(d.categories.map(key));
      const extra = d.categories.filter(c => !mine.has(key(c))).map(c => c.name);
      const missing = first.categories.filter(c => !theirs.has(key(c))).map(c => c.name);
      const parts = [];
      if (extra.length) parts.push(this.$t("exportMerge.extra", { names: extra.join("、") }));
      if (missing.length) parts.push(this.$t("exportMerge.missing", { names: missing.join("、") }));
      return parts.join("；");
    },
    /** on to the first ticked dataset's export wizard, the others ticked there */
    goExport() {
      const [first, ...others] = this.exportPick.chosen;
      if (first == null) return;
      hideModal("#exportPick");
      try {
        sessionStorage.setItem("dataset/pendingExport", JSON.stringify({ dataset: first, merge: others }));
      } catch {
        // the wizard then just does not open by itself
      }
      this.$router.push({ name: "dataset", params: { identifier: first } });
    },
    onImported({ datasetId, importTask }) {
      const query = importTask ? { importTask } : {};
      this.$router.push({ name: "dataset", params: { identifier: datasetId }, query });
    },
    openCreate() {
      this.create = { step: 1, touched: false, name: "", categories: [], task: "", replaceTrashed: false };
      if (this.$refs.categoryPicker) this.$refs.categoryPicker.reset();
      showModal("#createDataset");
      setTimeout(() => this.$refs.createName && this.$refs.createName.focus(), 400);
    },
    /** a step opens once the name is filled in */
    canGoCreateStep(step) {
      return step <= 1 || (!this.validDatasetName && !(this.trashedSameName && !this.create.replaceTrashed));
    },
    nextCreateStep() {
      this.create.touched = true;
      if (this.create.step < 4 && this.canGoCreateStep(this.create.step + 1)) this.create.step += 1;
    },
    createDataset() {
      if (this.create.name.trim().length < 1 || this.creating) return;
      const categories = [...this.create.categories];
      this.creating = true;
      const replace = !!(this.trashedSameName && this.create.replaceTrashed);
      Datasets.create(this.create.name.trim(), categories, this.create.task, replace)
        .then(response => {
          hideModal("#createDataset");
          this.$toastr.success(this.$t(response.data.scanned ? "datasets.createdScanning" : "datasets.created",
            { name: this.create.name.trim() }));
          this.updatePage();
        })
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          if (data.code === "in_trash") {
            // not known when the dialog opened: show the choice on the first step
            this.trashed = [...this.trashed.filter(t => t.id !== data.dataset_id),
              { id: data.dataset_id, name: this.create.name.trim(), images: data.images || 0 }];
            this.create.step = 1;
            return;
          }
          const message = { exists: "datasets.nameTaken", in_trash_other: "datasets.nameInOthersTrash" }[data.code];
          this.$toastr.error(message ? this.$t(message) : data.message || String(error), this.$t("datasets.creatingADataset"));
        })
        .finally(() => (this.creating = false));
    },
    restoreTrashed() {
      const target = this.trashedSameName;
      if (!target) return;
      this.creating = true;
      axios.post("/api/trash/restore", { items: [{ type: "dataset", ids: [target.id] }], include_parents: true })
        .then(() => {
          hideModal("#createDataset");
          this.$toastr.success(this.$t("datasets.restored", { name: target.name }));
          this.updatePage();
        })
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          this.$toastr.error(data.message || String(error));
        })
        .finally(() => (this.creating = false));
    }
  },
  watch: {
    user() {
      this.updatePage();
    },
    search() {
      clearTimeout(this.searchTimer);
      this.searchTimer = setTimeout(() => this.updatePage(1), 300);
    }
  },
  computed: {
    shownExportPick() {
      const q = this.exportPick.filter.trim().toLowerCase();
      if (!q) return this.exportPick.list;
      return this.exportPick.list.filter(d => d.name.toLowerCase().includes(q) || this.exportPick.chosen.includes(d.id));
    },
    exportPickImages() {
      return this.exportPick.list.filter(d => this.exportPick.chosen.includes(d.id)).reduce((n, d) => n + d.images, 0);
    },
    trashedSameName() {
      const name = this.create.name.trim();
      return name ? this.trashed.find(t => t.name === name) || null : null;
    },
    /** the top-level tab of the current folder */
    activeTop() {
      if (!this.parent || this.parent === "-") return this.parent;
      return this.parent.split("/")[0];
    },
    subPath() {
      return this.parent && this.parent !== "-" ? ancestors(this.parent) : [];
    },
    /** folders one level inside the current one */
    subChildren() {
      if (!this.parent || this.parent === "-") return [];
      const depth = this.parent.split("/").length + 1;
      return this.parents.filter(p => p.name.startsWith(this.parent + "/") && p.name.split("/").length === depth)
        .sort((a, b) => byName(a.name, b.name));
    },
    tabs() {
      const tabs = [{ key: "", label: this.$t("parents.all"), icon: "fa-th", count: this.total }];
      // top level only; deeper levels are shown under the tabs
      this.parents.filter(p => !p.name.includes("/"))
        .forEach(p => tabs.push({ key: p.name, label: p.name, icon: "fa-folder-o", count: p.count }));
      if (this.noParent) tabs.push({ key: "-", label: this.$t("parents.none"), icon: "fa-file-o", count: this.noParent });
      return tabs;
    },
    createStepLabels() {
      return [this.$t("datasets.datasetName2"), this.$t("datasetTask.label"),
        this.$t("datasets.defaultCategories"), this.$t("datasets.confirmStep")];
    },
    directory() {
      let closing = this.create.name.length > 0 ? "/" : "";
      return "/datasets/" + this.create.name + closing;
    },
    validDatasetName() {
      const name = this.create.name.trim();
      if (name.length === 0) return this.$t("datasets.nameRequired");
      // same rules as the server: the name is also a folder name
      if (name.startsWith(".") || /[/\\]/.test(name)) return this.$t("datasets.nameInvalid");
      if (this.allNames.includes(name)) return this.$t("datasets.nameTaken");
      return "";
    },
    user() {
      return this.$store.state.user.user;
    }
  },
  created() {
    this.updatePage();
  }
};
</script>

<style scoped>
.pick-list {
  max-height: 360px;
  overflow-y: auto;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  padding: 4px 8px;
}
.pick-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 2px;
  margin: 0;
  cursor: pointer;
}
.search-box {
  max-width: 320px;
}
.sub-chip {
  padding: 0 8px;
  font-size: 0.8rem;
  border-radius: 999px;
}
.parent-tabs {
  flex-wrap: wrap;
}
.parent-tabs .nav-link {
  padding: 6px 12px;
}
.help-icon {
  color: darkblue;
  font-size: 20px;
  display: inline;
}
</style>
