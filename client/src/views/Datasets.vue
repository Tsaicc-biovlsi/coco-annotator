<template>
  <div>
    <div style="padding-top: 55px" />

    <div
      class="album py-5 bg-light"
      style="overflow: auto; height: calc(100vh - 55px)"
    >
      <div class="container">
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
              data-bs-toggle="modal"
              data-bs-target="#createDataset"
            >
              {{ $t('datasets.create') }}
            </button>
            <button type="button" class="btn btn-primary" @click="$refs.importModal.open()">
              {{ $t('datasets.import') }}
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
        <p v-if="datasets.length < 1" class="text-center">
          {{ $t('datasets.youNeedToCreateA') }}
        </p>
        <div v-else style="background-color: gray">
          <Pagination :pages="pages" @pagechange="updatePage" />
          <div class="row bg-light">
            <DatasetCard
              v-for="dataset in datasets"
              :key="dataset.id"
              :dataset="dataset"
              :categories="categories"
            />
          </div>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="createDataset">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('datasets.creatingADataset') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <form>
              <div
                class="mb-3"
                :class="{ 'was-validated': validDatasetName.length !== 0 }"
              >
                <label>{{ $t('datasets.datasetName2') }}</label>
                <input
                  v-model="create.name"
                  class="form-control"
                  :placeholder="$t('datasets.datasetName')"
                  required
                />
                <div class="invalid-feedback">
                  {{ validDatasetName }}
                </div>
              </div>

              <div class="mb-3">
                <label>{{ $t('datasets.defaultCategories') }}</label>
                <TagsInput
                  v-model:value="create.categories"
                  element-id="createCategory"
                  :existing-tags="categoryTags"
                  :typeahead="true"
                  :typeahead-activation-threshold="0"
                ></TagsInput>
              </div>

              <div class="mb-3" required>
                <label>{{ $t('datasets.folderDirectory') }}</label>
                <input class="form-control" disabled :value="directory" />
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-primary"
              @click="createDataset"
            >
              {{ $t('datasets.createDataset') }}
            </button>
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
  </div>
</template>

<script>
import toastrs from "@/mixins/toastrs";
import Datasets from "@/models/datasets";
import AdminPanel from "@/models/admin";
import DatasetCard from "@/components/cards/DatasetCard.vue";
import Pagination from "@/components/Pagination.vue";
import TagsInput from "@/components/TagsInput.vue";
import ImportDatasetModal from "@/components/ImportDatasetModal.vue";

import { mapMutations } from "vuex";

export default {
  name: "Datasets",
  components: { DatasetCard, Pagination, TagsInput, ImportDatasetModal },
  mixins: [toastrs],
  data() {
    return {
      pages: 1,
      limit: 52,
      page: 1,
      create: {
        name: "",
        categories: []
      },
      datasets: [],
      subdirectories: [],
      categories: [],
      users: []
    };
  },
  methods: {
    ...mapMutations(["addProcess", "removeProcess"]),
    updatePage(page) {
      let process = "Loading datasets";
      this.addProcess(process);

      page = page || this.page;
      this.page = page;

      Datasets.allData({
        limit: this.limit,
        page: page
      }).then(response => {
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
    onImported({ datasetId, importTask }) {
      const query = importTask ? { importTask } : {};
      this.$router.push({ name: "dataset", params: { identifier: datasetId }, query });
    },
    createDataset() {
      if (this.create.name.length < 1) return;
      let categories = [];

      for (let key in this.create.categories) {
        categories.push(this.create.categories[key]);
      }
      Datasets.create(this.create.name, categories)
        .then(() => {
          this.create.name = "";
          this.create.categories = [];
          this.updatePage();
        })
        .catch(error => {
          this.axiosReqestError(
            "Creating Dataset",
            error.response.data.message
          );
        });
    }
  },
  watch: {
    user() {
      this.updatePage();
    }
  },
  computed: {
    directory() {
      let closing = this.create.name.length > 0 ? "/" : "";
      return "/datasets/" + this.create.name + closing;
    },
    categoryTags() {
      let tags = {};
      this.categories.forEach(category => {
        tags[category.name] = category.name;
      });
      return tags;
    },
    validDatasetName() {
      if (this.create.name.length === 0) return this.$t("datasets.nameRequired");
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
.help-icon {
  color: darkblue;
  font-size: 20px;
  display: inline;
}
</style>
