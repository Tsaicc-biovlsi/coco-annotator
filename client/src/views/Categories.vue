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
          <Pagination :pages="pages" @pagechange="updatePage" />

          <div class="row">
            <CategoryCard
              v-for="category in categories"
              :key="category.id"
              :category="category"
            />
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
                <input
                  v-model="newCategorySupercategory"
                  class="form-control"
                  :placeholder="$t('categories.supercategory')"
                />
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
import Pagination from "@/components/Pagination.vue";
import KeypointsDefinition from "@/components/KeypointsDefinition.vue";

import { mapMutations } from "vuex";

export default {
  name: "Categories",
  components: { CategoryCard, Pagination, KeypointsDefinition },
  mixins: [toastrs],
  data() {
    return {
      docsUrl: docsSection("第一次使用"),
      categoryCount: 0,
      pages: 1,
      page: 1,
      limit: 50,
      range: 11,
      newCategoryName: "",
      newCategorySupercategory: "",
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
    updatePage(page) {
      let process = "Loading categories";
      this.addProcess(process);

      page = page || this.page;
      this.page = page;

      Category.allData({
        page: page,
        limit: this.limit
      })
        .then(response => {
          this.categories = response.data.categories;
          this.page = response.data.pagination.page;
          this.pages = response.data.pagination.pages;
          this.categoryCount = response.data.pagination.total;
        })
        .finally(() => this.removeProcess(process));
    },
    createCategory() {
      if (this.newCategoryName.length < 1) return;

      Category.create({
        name: this.newCategoryName,
        supercategory: this.newCategorySupercategory,
        color: this.newCategoryColor,
        keypoint_labels: this.newCategoryKeypoint.labels,
        keypoint_edges: this.newCategoryKeypoint.edges,
        keypoint_colors: this.newCategoryKeypoint.colors,
      })
        .then(() => {
          this.newCategoryName = "";
          this.newCategorySupercategory = "";
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
    previousPage() {
      this.page -= 1;
      if (this.page < 1) {
        this.page = 1;
      }
    },
    nextPage: function() {
      this.page += 1;
      if (this.page > this.pages) {
        this.page = this.pages;
      }
    }
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

.help-icon {
  color: darkblue;
  font-size: 20px;
  display: inline;
}
</style>
