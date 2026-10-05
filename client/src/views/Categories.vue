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
          <div class="d-flex flex-wrap align-items-center gap-2 mb-3">
            <input
              v-model="search"
              class="form-control form-control-sm search-box"
              :placeholder="$t('parents.searchCategories')"
            />
            <div v-if="grouped" class="btn-group btn-group-sm ms-auto">
              <button type="button" class="btn btn-outline-secondary" @click="collapsed = {}">
                <i class="fa fa-plus-square-o" /> {{ $t('parents.expandAll') }}
              </button>
              <button type="button" class="btn btn-outline-secondary" @click="collapseAll">
                <i class="fa fa-minus-square-o" /> {{ $t('parents.collapseAll') }}
              </button>
            </div>
          </div>

          <div v-for="g in groups" :key="g.key" class="mb-2">
            <div v-if="grouped" class="group-title d-flex align-items-center gap-2" @click="toggleGroup(g.key)">
              <i class="fa fa-fw" :class="collapsed[g.key] ? 'fa-caret-right' : 'fa-caret-down'" />
              <i class="fa" :class="g.parent ? 'fa-folder-open-o' : 'fa-file-o'" />
              <strong>{{ g.parent || $t('parents.none') }}</strong>
              <span class="badge rounded-pill text-bg-secondary">{{ g.items.length }}</span>
              <button
                v-if="g.parent"
                type="button"
                class="btn btn-link btn-sm p-0 ms-1"
                :title="$t('parents.addHere', { name: g.parent })"
                @click.stop="openCreate([g.parent])"
              ><i class="fa fa-plus" /> {{ $t('parents.addHereShort') }}</button>
            </div>
            <div v-show="!collapsed[g.key]" class="row mt-2">
              <CategoryCard
                v-for="category in g.items"
                :key="g.key + '-' + category.id"
                :category="category"
                :uid="grouped ? '-' + g.index : ''"
                :group-parent="g.parent"
                :known-parents="knownParents"
                @changed="updatePage"
              />
            </div>
          </div>
          <p v-if="!groups.length" class="text-center text-muted">{{ $t('exportCategories.noMatch') }}</p>
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
import { allParents, groupByParent, matchesSearch } from "@/libs/parents";
import { Modal } from "bootstrap";

import { mapMutations } from "vuex";

export default {
  name: "Categories",
  components: { CategoryCard, KeypointsDefinition, ParentInput },
  mixins: [toastrs],
  data() {
    return {
      docsUrl: docsSection("第一次使用"),
      categoryCount: 0,
      search: "",
      collapsed: {},
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
    groups() {
      const q = this.search.trim();
      const shown = this.categories.filter(c => matchesSearch(c, q));
      return groupByParent(shown).map((g, index) => ({ ...g, index, key: g.parent === null ? "-" : "p:" + g.parent }));
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
    toggleGroup(key) {
      this.collapsed = { ...this.collapsed, [key]: !this.collapsed[key] };
    },
    collapseAll() {
      const next = {};
      this.groups.forEach(g => (next[g.key] = true));
      this.collapsed = next;
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

.group-title {
  cursor: pointer;
  border-bottom: 1px solid #dee2e6;
  padding: 4px 2px;
  user-select: none;
}

.help-icon {
  color: darkblue;
  font-size: 20px;
  display: inline;
}
</style>
