<template>
  <div>
    <div style="padding-top: 55px" />
    <div
      class="album py-5 bg-light"
      style="overflow: auto; height: calc(100vh - 55px)"
    >
      <div class="container">
        <h2 class="text-center">
          {{ $t('categories.categories') }}
          <i
            class="fa fa-question-circle help-icon"
            data-bs-toggle="modal"
            data-bs-target="#helpCategories"
            aria-hidden="true"
          />
        </h2>

        <p class="text-center">
          <i18n-t keypath="categories.loaded" tag="span"><template #n><strong>{{ categoryCount }}</strong></template></i18n-t>
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
              data-bs-toggle="modal"
              data-bs-target="#createCategories"
            >
              {{ $t('categories.create') }}
            </button>
            <button type="button" class="btn btn-secondary" @click="updatePage">
              {{ $t('categories.refresh') }}
            </button>
          </div>
        </div>

        <hr />

        <p v-if="categories.length < 1" class="text-center">
          {{ $t('categories.youNeedToCreateA') }}
        </p>
        <div v-else>
          <!-- one tab per parent category -->
          <ul v-if="grouped" class="nav nav-tabs mb-3 parent-tabs">
            <li v-for="g in tabs" :key="g.key" class="nav-item">
              <a href="#" class="nav-link" :class="{ active: g.key === currentKey }" @click.prevent="selectTab(g.key)">
                <i class="fa" :class="g.key === '*' ? 'fa-th' : g.parent ? 'fa-folder-o' : 'fa-file-o'" />
                {{ g.label }}
                <span class="badge rounded-pill text-bg-secondary ms-1">{{ g.items.length }}</span>
              </a>
            </li>
          </ul>

          <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
            <input
              v-model="search"
              class="form-control form-control-sm search-box"
              :placeholder="$t('parents.searchCategories')"
            />
            <button
              v-if="current && current.parent"
              type="button"
              class="btn btn-sm btn-outline-success"
              @click="openCreate([current.parent])"
            ><i class="fa fa-plus" /> {{ $t('parents.addHere', { name: current.parent }) }}</button>
            <span v-if="currentItems.length" class="small text-muted ms-auto">
              {{ $t('parents.showing', { from: pageStart + 1, to: Math.min(pageStart + perPage, currentItems.length), n: currentItems.length }) }}
            </span>
          </div>

          <div class="row">
            <CategoryCard
              v-for="category in pageItems"
              :key="currentKey + '-' + category.id"
              :category="category"
              :uid="'-' + currentIndex"
              :group-parent="current ? current.parent : null"
              :known-parents="knownParents"
              @changed="updatePage"
            />
          </div>
          <p v-if="!currentItems.length" class="text-center text-muted">{{ $t('exportCategories.noMatch') }}</p>

          <div v-if="pageCount > 1" class="d-flex justify-content-center">
            <Pagination :key="currentKey + '|' + search + '|' + pageCount" :pages="pageCount" @pagechange="p => (page = p)" />
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="createCategories">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('categories.creatingACategory') }}</h5>
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
                <label>{{ $t('categories.name2') }}</label>
                <input
                  v-model="newCategoryName"
                  class="form-control"
                  :class="{'is-invalid': newCategoryName.trim().length === 0}"
                  required="true"
                  :placeholder="$t('categories.name')"
                />
              </div>

              <div class="mb-3">
                <label>{{ $t('categories.supercategory2') }}</label>
                <ParentInput v-model="newCategoryParents" :known="knownParents" />
                <div class="form-text">{{ $t('parents.hint') }}</div>
              </div>

              <div class="mb-3 row">
                <label class="col-sm-2 col-form-label">{{ $t('categories.color') }}</label>
                <div class="col-sm-9">
                  <input v-model="newCategoryColor" type="color" class="form-control form-control-color w-100" />
                </div>
              </div>

              <div class="mb-3">
                <KeypointsDefinition ref="keypoints"
                  v-model:value="newCategoryKeypoint"
                  element-id="keypoints"
                  :placeholder="$t('categories.addAKeypoint')"
                ></KeypointsDefinition>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!isFormValid"
              :class="{disabled: !isFormValid}"
              @click="createCategory"
            >
              {{ $t('categories.createCategory') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('categories.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="helpCategories">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('categories.categories') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            {{ $t('categories.moreInformationCanBeFound') }}
            <a :href="docsUrl" target="_blank" rel="noopener">
              {{ $t('categories.gettingStartedSection') }}
            </a>.
            <hr />
            <h6>{{ $t('categories.whatIsACategory') }}</h6>

            <hr />
            <h6>{{ $t('categories.howDoICreateOne') }}</h6>
            {{ $t('categories.clickOnTheCreateButton') }}
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('categories.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import toastrs from "@/mixins/toastrs";
import { docsSection } from "@/links";

import Category from "@/models/categories";
import CategoryCard from "@/components/cards/CategoryCard.vue";
import KeypointsDefinition from "@/components/KeypointsDefinition.vue";
import ParentInput from "@/components/ParentInput.vue";
import Pagination from "@/components/Pagination.vue";
import { allParents, groupByParent, matchesSearch } from "@/libs/parents";
import { Modal } from "bootstrap";

import { mapMutations } from "vuex";

function readTab() {
  try {
    return localStorage.getItem("categories.tab") || "";
  } catch {
    return "";
  }
}

export default {
  name: "Categories",
  components: { CategoryCard, KeypointsDefinition, ParentInput, Pagination },
  mixins: [toastrs],
  data() {
    return {
      docsUrl: docsSection("第一次使用"),
      categoryCount: 0,
      search: "",
      tab: readTab(),
      page: 1,
      perPage: 16,
      newCategoryName: "",
      newCategoryParents: [],
      newCategoryColor: null,
      newCategoryKeypoint: {
        labels: [],
        edges: [],
        colors: []
      },
      categories: [],
      status: {
        data: { state: true, message: "Loading categories" }
      }
    };
  },
  computed: {
    knownParents() {
      return allParents(this.categories);
    },
    /** with no parents at all the page is one plain list */
    grouped() {
      return this.knownParents.length > 0;
    },
    /** one tab per parent, then "no parent", then all */
    tabs() {
      const q = this.search.trim();
      const shown = this.categories.filter(c => matchesSearch(c, q));
      const tabs = groupByParent(shown).map(g => ({
        ...g, key: g.parent === null ? "-" : "p:" + g.parent, label: g.parent === null ? this.$t("parents.none") : g.parent
      }));
      tabs.push({ key: "*", parent: null, label: this.$t("parents.all"), items: shown });
      return tabs;
    },
    currentKey() {
      if (!this.grouped) return "*";
      return this.tabs.some(t => t.key === this.tab) ? this.tab : this.tabs[0].key;
    },
    currentIndex() {
      return this.tabs.findIndex(t => t.key === this.currentKey);
    },
    current() {
      return this.tabs[this.currentIndex] || null;
    },
    currentItems() {
      return this.current ? this.current.items : [];
    },
    pageCount() {
      return Math.max(1, Math.ceil(this.currentItems.length / this.perPage));
    },
    pageStart() {
      return (Math.min(this.page, this.pageCount) - 1) * this.perPage;
    },
    pageItems() {
      return this.currentItems.slice(this.pageStart, this.pageStart + this.perPage);
    },
    isFormValid() {
      return (
        this.newCategoryName.length !== 0 &&
        this.$refs &&
        this.$refs.keypoints &&
        this.$refs.keypoints.valid
      );
    }
  },
  watch: {
    search() {
      this.page = 1;
    }
  },
  methods: {
    ...mapMutations(["addProcess", "removeProcess"]),
    updatePage() {
      let process = "Loading categories";
      this.addProcess(process);

      // all of them: they are shown grouped by parent
      Category.allData({ page: 1, limit: 100000 })
        .then(response => {
          this.categories = response.data.categories;
          this.categoryCount = response.data.pagination.total;
        })
        .finally(() => this.removeProcess(process));
    },
    selectTab(key) {
      this.tab = key;
      this.page = 1;
      try {
        localStorage.setItem("categories.tab", key);
      } catch {
        // private mode etc.: the tab is just not remembered
      }
    },
    openCreate(parents) {
      this.newCategoryParents = [...parents];
      Modal.getOrCreateInstance(document.getElementById("createCategories")).show();
    },
    createCategory() {
      if (this.newCategoryName.length < 1) return;

      Category.create({
        name: this.newCategoryName,
        supercategories: this.newCategoryParents,
        color: this.newCategoryColor,
        keypoint_labels: this.newCategoryKeypoint.labels,
        keypoint_edges: this.newCategoryKeypoint.edges,
        keypoint_colors: this.newCategoryKeypoint.colors,
      })
        .then(() => {
          this.newCategoryName = "";
          this.newCategoryParents = [];
          this.newCategoryColor = null;
          this.newCategoryKeypoint = {};
          this.updatePage();
        })
        .catch(error => {
          this.axiosReqestError(
            "Creating Category",
            error.response.data.message
          );
        });
    },
  },
  created() {
    this.updatePage();
  }
};
</script>

<style scoped>
.card-img-overlay {
  padding: 0 10px 0 0;
}

.icon-more {
  width: 10%;
  margin: 3px 0;
  padding: 0;
  float: right;
  color: black;
}

.search-box {
  max-width: 320px;
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
