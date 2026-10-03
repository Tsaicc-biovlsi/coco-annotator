<template>
  <div @mousemove="mouseMove">
    <div style="padding-top: 55px" />
    
    <div
      class="bg-light"
      :style="{ 'margin-left': sidebar.width + 'px' }"
    >
      <nav class="nav border-bottom shadow-sm" style="background-color: #4b5162">
        <a class="btn tab" @click="tab = 'images'" :style="{'color': tab == 'images' ? 'white' : 'darkgray'}">
          <i class="fa fa-picture-o" aria-hidden="true"></i> {{ $t('dataset.images') }}
        </a>
        <a class="btn tab" @click="tab = 'exports'" :style="{'color': tab == 'exports' ? 'white' : 'darkgray'}">
          <i class="fa fa-share" aria-hidden="true"></i> {{ $t('dataset.exports') }}
        </a>
        <a class="btn tab" @click="tab = 'members'" :style="{'color': tab == 'members' ? 'white' : 'darkgray'}">
          <i class="fa fa-users" aria-hidden="true"></i> {{ $t('dataset.members') }}
        </a>
        <a class="btn tab" @click="tab = 'statistics'" :style="{'color': tab == 'statistics' ? 'white' : 'darkgray'}">
          <i class="fa fa-bar-chart" aria-hidden="true"></i> {{ $t('dataset.statistics') }}
        </a>
        <a class="btn tab" @click="tab = 'settings'" :style="{'color': tab == 'settings' ? 'white' : 'darkgray'}">
          <i class="fa fa-cog" aria-hidden="true"></i> {{ $t('dataset.settings') }}
        </a>
      </nav>
    
      <div class="bg-light text-start" style="overflow: auto; height: calc(100vh - 100px); margin: 10px">
        <div class="container" v-show="tab == 'images'">
          
          <ol class="breadcrumb">
            <li class="breadcrumb-item"></li>
            <li class="breadcrumb-item active">
              <button class="btn btn-sm btn-link" @click="folders = []">
                {{ dataset.name }}
              </button>
            </li>
            <li
              v-for="(folder, folderId) in folders"
              :key="folderId"
              class="breadcrumb-item"
            >
              <button
                class="btn btn-sm btn-link"
                :disabled="folders[folders.length - 1] === folder"
                @click="removeFolder(folder)"
              >
                {{ folder }}
              </button>
            </li>
          </ol>

          <p class="text-center" v-if="images.length < 1">
            {{ $t('dataset.noImagesFoundInDirectory') }}
          </p>
          <div v-else>
            <Pagination :pages="pages" @pagechange="updatePage" />
            <div class="row">
              <ImageCard v-for="image in images" :key="image.id" :image="image" />
            </div>
            <Pagination :pages="pages" @pagechange="updatePage" />
          </div>

        </div>
        <div class="container" v-show="tab == 'exports'">
          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.exports') }}</b></h6>
            
            <div class="d-flex align-items-start text-muted pt-3" v-for="exp in datasetExports" :key="exp.id">
              <div class="flex-grow-1 lh-125 border-bottom border-gray">
                  {{ exp.id }}. {{ $t('dataset.exportedAgo', { time: $ago(exp.ago) }) }}
                  <div style="display: inline">
                    <span
                      v-for="tag in exp.tags"
                      :key="tag"
                      class="badge text-bg-secondary"
                      style="margin: 1px"
                    >
                      {{tag}}
                    </span>
                  </div>
                  <button 
                    class="btn btn-sm btn-success"
                    style="float: right; margin: 2px; padding: 2px"
                    @click="downloadExport(exp.id)"
                  >
                    {{ $t('dataset.download') }}
                  </button>
              </div>
            </div>
          </div>
        </div>

        <div class="container" v-show="tab == 'members'">

          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.inviteMembers') }}</b></h6>
            
          </div>
          
          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.existingMembers') }}</b></h6>
            
            <div class="d-flex align-items-start text-muted pt-3" v-for="user in users" :key="user.username">
              <img :src="userAvatar" class="me-2 rounded" style="width: 32px; height: 32px;">
              <div class="flex-grow-1 pb-3 mb-0 small lh-125 border-bottom border-gray">
                <div class="d-flex justify-content-between align-items-center w-100">
                  <div class="text-gray-dark">
                    <strong>{{ user.name }}</strong> @{{user.username}}
                  </div>
                  <a href="#">{{ user.group }}</a>
                </div>
                <span class="d-block">{{ $t('dataset.lastSeen', { time: new Date(user.last_seen['$date']).toISOString().slice(0, 19).replace('T', ' ') }) }}</span>
              </div>
            </div>
          </div>

        </div>
        <div class="container" v-show="tab == 'statistics'">
          <div v-if="stats == null">
            {{ $t('dataset.crunchingNumbers') }}
          </div>

          <div v-else>
            <div class="row">
              
              <div v-if="stats.total" class="card my-3 p-3 shadow-sm col-3 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.total') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.total)" :key="stat">
                  <strong class="col-8">{{ $tr('stat', stat) }}:</strong>
                  <span class="col-4">{{stats.total[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.average" class="card my-3 p-3 shadow-sm col-4 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.average') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.average)" :key="stat">
                  <strong class="col-8">{{ $tr('stat', stat) }}:</strong>
                  <span class="col-4">{{stats.average[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.categories" class="card my-3 p-3 shadow-sm col-4 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.annotationsPerCategory') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.categories)" :key="stat">
                  <strong class="col-8">{{stat}}:</strong>
                  <span class="col-4">{{stats.categories[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.images_per_category" class="card my-3 p-3 shadow-sm col-4 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.annotatedImagesPerCategory') }}</b></h6>
                <div class="row" v-for="stat in Object.keys(stats.images_per_category)" :key="stat">
                  <strong class="col-8">{{stat}}:</strong>
                  <span class="col-4">{{stats.images_per_category[stat].toFixed(0)}}</span>
                </div>
              </div>

              <div v-if="stats.users" class="card my-3 p-3 shadow-sm col-6 me-2">
                <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.annotationsPerUser') }}</b></h6>
                <h6 class="row border-bottom border-gray pb-2">
                    <span class="col-4">{{ $t('dataset.username') }}</span>
                    <span class="col-4">{{ $t('dataset.annotations') }}</span>
                    <span class="col-4">{{ $t('dataset.images') }}</span>
                </h6>
                <div class="row" v-for="stat in Object.keys(stats.users)" :key="stat">
                  <strong class="col-4">{{stat}}:</strong>
                  <span class="col-4">{{stats.users[stat]["annotations"].toFixed(0)}}</span>
                  <span class="col-4">{{stats.users[stat]["images"].toFixed(0)}}</span>
                </div>
              </div>

            </div>
            
          </div>
        </div>
        <div class="container" v-show="tab == 'settings'">
          <div class="card my-3 p-3 shadow-sm me-2">
            <h6 class="border-bottom border-gray pb-2"><b>{{ $t('dataset.metadata') }}</b></h6>
            
            <button 
              class="btn btn-sm w-100 btn-danger"
              @click="resetMetadata"
            >
              {{ $t('dataset.restAllMetadata') }}
            </button>
          </div>
        </div>

      </div>
    </div>

    <div
      id="filter"
      ref="sidebar"
      class="sidebar"
      :style="{ width: sidebar.width + 'px' }"
    >
      <div style="padding-top: 10px" />
      <h3>{{ dataset.name }}</h3>
      <p class="text-center" style="color: lightgray">
        <i18n-t keypath="dataset.totalImages" tag="span">
          <template #images><strong style="color: white">{{ imageCount }}</strong></template>
          <template #pages><strong style="color: white">{{ pages }}</strong></template>
        </i18n-t>
      </p>
      <div class="row justify-content-md-center sidebar-section-buttons">
        <button
          type="button"
          class="btn btn-secondary w-100"
          @click="createScanTask"
        >
          <div v-if="scan.id != null" class="progress">
            <div
              class="progress-bar bg-secondary"
              :style="{ 'width': `${scan.progress}%` }"
            >
              {{ $t('dataset.scanning') }}
            </div>
          </div>
          <div v-else>{{ $t('dataset.scan') }}</div>
        </button>

        <button
          type="button"
          class="btn btn-primary w-100"
          @click="importModal"
        >
          <div v-if="importing.id != null" class="progress">
            <div
              class="progress-bar bg-primary"
              :style="{ 'width': `${importing.progress}%` }"
            >
              {{ $t('dataset.importing') }}
            </div>
          </div>
          <div v-else>{{ $t('dataset.importCoco') }}</div>
        </button>

        <button
          type="button"
          class="btn btn-dark w-100"
          @click="exportModal"
        >
          <div v-if="exporting.id != null" class="progress">
            <div
              class="progress-bar bg-dark"
              :style="{ 'width': `${exporting.progress}%` }"
            >
              {{ $t('dataset.exporting') }}
            </div>
          </div>
          <div v-else>{{ $t('dataset.exportCoco') }}</div>
        </button>
      </div>
      <hr>
      <h6 class="sidebar-title text-center">{{ $t('dataset.subdirectories') }}</h6>
      <div class="sidebar-section" style="max-height: 30%; color: lightgray">
        <div v-if="subdirectories.length > 0">
          <button
            v-for="(subdirectory, subId) in subdirectories"
            :key="subId"
            class="btn badge rounded-pill text-bg-primary category-badge"
            style="margin: 2px"
            @click="folders.push(subdirectory)"
          >
            {{ subdirectory }}
          </button>
        </div>
        <p v-else style="margin: 0; font-size: 13px; color: gray">
          {{ $t('dataset.noSubdirectoryFound') }}
        </p>
      </div>
      <hr>
      <h6 class="sidebar-title text-center">{{ $t('dataset.filteringOptions') }}</h6>
      <div
        class="sidebar-section"
        style="max-height: 30%; color: lightgray"
      >
        <PanelString :name="$t('dataset.contains')" v-model:value="query.file_name__icontains" @submit="updatePage" />
        <PanelToggle :name="$t('dataset.showAnnotated')" v-model:value="panel.showAnnotated" />
        <PanelToggle :name="$t('dataset.showNotAnnotated')" v-model:value="panel.showNotAnnotated" />
        <PanelDropdown :name="$t('dataset.order')" v-model:value="order" :values="orderTypes" />
      </div>
        <div
          class="sidebar-section"
          style="max-height: 30%; color: lightgray"
        >
          <div class="mb-3">
            <label>{{ $t('dataset.showAnnotatedCategories') }} </label>
            <TagsInput
              v-model:value="selected.categories"
              element-id="selectedCategories"
              :title="$t('dataset.onlyShowsImagesAnnotatedWith')"
              :existing-tags="categoryTags"
              :typeahead="true"
              :typeahead-activation-threshold="0"
            ></TagsInput>
          </div>
      </div>
    </div>


    <div class="modal fade" tabindex="-1" role="dialog" id="cocoUpload">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('dataset.uploadCocoAnnotaitons') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <form>
              <div class="mb-3">
                <label for="coco">{{ $t('dataset.cocoAnnotationFileJson') }}</label>
                <input type="file" class="form-control-file" id="coco" />
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              @click="importCOCO"
              data-bs-dismiss="modal"
            >
              {{ $t('dataset.upload') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('dataset.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="exportDataset">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('dataset.exportTitle', { name: dataset.name }) }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <form>
              <div class="mb-3">
                <label>{{ $t('dataset.categoriesEmptyExportAll') }}</label>
                <TagsInput
                  v-model:value="exporting.categories"
                  element-id="exportCategories"
                  :existing-tags="categoryTags"
                  :typeahead="true"
                  :typeahead-activation-threshold="0"
                ></TagsInput>
              </div>
              <div class="form-check d-inline-flex align-items-center gap-2 ps-0">
                <input type="checkbox" class="form-check-input m-0" id="exportWithEmpty"
                  v-model="exporting.with_empty_images">
                <label class="form-check-label mb-0" for="exportWithEmpty">{{ $t('dataset.exportWithNotAnnotatedImages') }}</label>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              @click="exportCOCO"
            >
              {{ $t('dataset.export') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('dataset.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import userAvatar from "@/assets/user.png";
import { hideModal, showModal } from "@/libs/modal";
import toastrs from "@/mixins/toastrs";
import Dataset from "@/models/datasets";
import Export from "@/models/exports";
import ImageCard from "@/components/cards/ImageCard.vue";
import Pagination from "@/components/Pagination.vue";
import PanelString from "@/components/PanelInputString.vue";
import PanelToggle from "@/components/PanelToggle.vue";
import PanelDropdown from "@/components/PanelInputDropdown.vue"
import TagsInput from "@/components/TagsInput.vue";

import { mapMutations } from "vuex";


export default {
  name: "Dataset",
  components: {
    ImageCard,
    Pagination,
    PanelString,
    PanelToggle,
    PanelDropdown,
    TagsInput
  },
  mixins: [toastrs],
  props: {
    identifier: {
      type: [Number, String],
      required: true
    }
  },
  data() {
    return {
      userAvatar,
      pages: 1,
      limit: 52,
      imageCount: 0,
      categories: [],
      images: [],
      folders: [],
      dataset: {
        id: 0
      },
      users: [],
      subdirectories: [],
      status: {
        data: { state: true, message: "Loading data" }
      },
      mouseDown: false,
      sidebar: {
        drag: false,
        width: window.innerWidth * 0.2,
        canResize: false
      },
      scan: {
        progress: 0,
        id: null
      },
      importing: {
        progress: 0,
        id: null
      },
      exporting: {
        categories: [],
        progress: 0,
        with_empty_images: false,
        id: null
      },
      selected: {
        categories: []
      },
      datasetExports: [],
      tab: "images",
      order: "file_name",
      orderTypes: {
        file_name: "File Name",
        id: "Id",
        path: "File Path"
      },
      query: {
        file_name__icontains: "",
        ...this.$route.query
      },
      panel: {
        showAnnotated: true,
        showNotAnnotated: true
      },
      stats: null
    };
  },
  methods: {
    ...mapMutations(["addProcess", "removeProcess"]),
    updatePage(page) {
      let process = "Loading images from dataset";
      this.addProcess(process);

      Dataset.getData(this.dataset.id, {
        page: page,
        limit: this.limit,
        folder: this.folders.join("/"),
        ...this.query,
        annotated: this.queryAnnotated,
        category_ids__in: encodeURI(this.selected.categories),
        order: this.order
      })
        .then(response => {
          let data = response.data;

          this.images = data.images;
          this.dataset = data.dataset;
          this.categories = data.categories;

          this.imageCount = data.total;
          this.pages = data.pages;

          this.subdirectories = data.subdirectories;
          // this.scan.id = data.scanId;
          // this.generate.id = data.generateId;
          // this.importing.id = data.importId;
          // this.exporting.id = data.exportId;
        })
        .catch(error => {
          this.axiosReqestError("Loading Dataset", error.response.data.message);
        })
        .finally(() => this.removeProcess(process));
    },
    getUsers() {
      Dataset.getUsers(this.dataset.id).then(response => {
        this.users = response.data;
      });
    },
    downloadExport(id) {
      Export.download(id, this.dataset.name);
    },
    getExports() {
      Dataset.getExports(this.dataset.id).then(response => {
        this.datasetExports = response.data;
      });
    },
    resetMetadata() {
      let r = confirm("You can not undo reseting of all metadata in"
        + "this dataset. This includes metadata of images"
        + "and annotations.");
      
      if (r) {
        Dataset.resetMetadata(this.dataset.id);
      }
    },
    getStats() {
      Dataset.getStats(this.dataset.id).then(response => {
        this.stats = response.data;
      });
    },
    createScanTask() {
      if (this.scan.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.scan.id } });
        return;
      }

      Dataset.scan(this.dataset.id)
        .then(response => {
          let id = response.data.id;
          this.scan.id = id;
        })
        .catch(error => {
          this.axiosReqestError(
            "Scanning Dataset",
            error.response.data.message
          );
        });
    },
    exportModal() {
      if (this.exporting.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.exporting.id } });
        return;
      }
      showModal("#exportDataset");
    },
    exportCOCO() {
      hideModal("#exportDataset");
      Dataset.exportingCOCO(this.dataset.id, this.exporting.categories, this.exporting.with_empty_images)
        .then(response => {
          let id = response.data.id;
          this.exporting.id = id;
        })
        .catch(error => {
          this.axiosReqestError("Exporting COCO", error.response.data.message);
        });
    },
    removeFolder(folder) {
      let index = this.folders.indexOf(folder);
      this.folders.splice(index + 1, this.folders.length);
    },
    importModal() {
      if (this.importing.id != null) {
        this.$router.push({ path: "/tasks", query: { id: this.importing.id } });
        return;
      }

      showModal("#cocoUpload");
    },
    importCOCO() {
      let uploaded = document.getElementById("coco");
      Dataset.uploadCoco(this.dataset.id, uploaded.files[0])
        .then(response => {
          let id = response.data.id;
          this.importing.id = id;
        })
        .catch(error => {
          this.axiosReqestError("Importing COCO", error.response.data.message);
        });
    },
    mouseMove(event) {
      let element = this.$refs.sidebar;

      let sidebarWidth = element.offsetWidth;
      let clickWidth = event.x;
      let pixelsFromSide = Math.abs(sidebarWidth - clickWidth);

      this.sidebar.drag = pixelsFromSide < 4;

      if (this.sidebar.canResize) {
        event.preventDefault();
        let max = window.innerWidth * 0.5;
        this.sidebar.width = Math.min(Math.max(event.x, 150), max);
        localStorage.setItem("dataset/sideWidth", this.sidebar.width)
      }
    },
    startDrag() {
      this.mouseDown = true;
      this.sidebar.canResize = this.sidebar.drag;
    },
    stopDrag() {
      this.mouseDown = false;
      this.sidebar.canResize = false;
    }
  },
  computed: {
    queryAnnotated() {
      let showAnnotated = this.panel.showAnnotated;
      let showNotAnnotated = this.panel.showNotAnnotated;

      if (showAnnotated && showNotAnnotated) return null;
      if (!showAnnotated && !showNotAnnotated) return " ";

      return showAnnotated;
    },
    categoryTags() {
      let tags = {};
      this.categories.forEach(c => tags[c.id] = c.name);
      return tags;
    }
  },
  sockets: {
    taskProgress(data) {
      if (data.id === this.scan.id) {
        this.scan.progress = data.progress;
      }

      if (data.id === this.importing.id) {
        this.importing.progress = data.progress;
      }

      if (data.id === this.exporting.id) {
        this.exporting.progress = data.progress;
      }
    },
    annotating(data) {
      let image = this.images.find(i => i.id == data.image_id);
      if (image == null) return;

      if (data.active) {
        let found = image.annotating.indexOf(data.username);
        if (found < 0) {
          image.annotating.push(data.username);
        }
      } else {
        image.annotating.splice(image.annotating.indexOf(data.username), 1);
      }
    }
  },
  watch: {
    tab(tab) {
      localStorage.setItem("dataset/tab", tab);
      if (tab == "members") this.getUsers();
      if (tab == "statistics") this.getStats();
      if (tab == "exports") this.getExports();
    },
    order(order) {
      localStorage.setItem("dataset/order", order);
      this.updatePage();
    },
    queryAnnotated() {
      this.updatePage();
    },
    "selected.categories": {
      deep: true,
      handler(val) {
        this.updatePage();
      }
    },
    folders: {
      deep: true,
      handler() {
        this.updatePage();
      }
    },
    "sidebar.drag"(canDrag) {
      let el = this.$refs.sidebar;
      if (canDrag) {
        this.$el.style.cursor = "ew-resize";
        el.style.borderRight = "4px solid #383c4a";
      } else {
        this.$el.style.cursor = "default";
        el.style.borderRight = "";
      }
    },
    "scan.progress"(progress) {
      if (progress >= 100) {
        setTimeout(() => {
          this.scan.progress = 0;
          this.scan.id = null;
        }, 1000);
      }
    },
    "importing.progress"(progress) {
      if (progress >= 100) {
        setTimeout(() => {
          this.importing.progress = 0;
          this.importing.id = null;
        }, 1000);
      }
    },
    "exporting.progress"(progress) {
      if (progress >= 100) {
        setTimeout(() => {
          this.exporting.progress = 0;
          this.exporting.id = null;

          this.getExports();
        }, 1000);
      }
    }
  },
  beforeRouteUpdate() {
    this.dataset.id = parseInt(this.identifier);
    this.updatePage();
  },
  created() {
    let tab = localStorage.getItem("dataset/tab");
    let order = localStorage.getItem("dataset/order");
    let sideWidth = localStorage.getItem("dataset/sideWidth");
    
    if (sideWidth !== null) this.sidebar.width = parseInt(sideWidth);
    if (tab !== null) this.tab = tab;
    if (order !== null) this.order = order;

    this.dataset.id = parseInt(this.identifier);
    this.updatePage();
  },
  mounted() {
    window.addEventListener("mouseup", this.stopDrag);
    window.addEventListener("mousedown", this.startDrag);
  },
  unmounted() {
    window.removeEventListener("mouseup", this.stopDrag);
    window.removeEventListener("mousedown", this.startDrag);
  }
};
</script>

<style scoped>
.breadcrumb {
  padding: 0px;
  margin: 5px 0;
}

.btn-link {
  padding: 0px;
}

.sidebar .title {
  color: white;
}

.progress {
  padding: 2px;
  height: 24px;
}

.sidebar {
  height: 100%;
  position: fixed;
  color: white;
  z-index: 1;
  top: 0;
  left: 0;
  background-color: #4b5162;
  overflow-x: hidden;
  padding-top: 60px;
}

.sidebar .closebtn {
  position: absolute;
  top: 0;
  right: 25px;
  font-size: 36px;
  margin-left: 50px;
}

.sidebar-title {
  color: white;
}

.sidebar-section-buttons {
  margin: 5px;
}

.sidebar-section {
  margin: 5px;
  border-radius: 5px;
  background-color: #383c4a;
  padding: 0 5px 2px 5px;
  overflow: auto;
}
</style>
