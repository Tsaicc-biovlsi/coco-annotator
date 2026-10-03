<template>
  <div class="col-md-3">
    <div class="card mb-4 box-shadow" @click="onCardClick">
      <div class="card-body">
        <span class="d-inline-block text-truncate" style="max-width: 75%; float: left">
          <i class="fa fa-circle color-icon" aria-hidden="true" :style="{ color: category.color }" />
          <strong class="card-title">{{ category.name }}</strong>
        </span>

        <i
          class="card-text fa fa-ellipsis-v fa-x icon-more"
          :id="'dropdownCategory' + category.id"
          data-bs-toggle="dropdown"
          aria-haspopup="true"
          aria-expanded="false"
          aria-hidden="true"
        />

        <br />

        <div>
          <p v-if="category.numberAnnotations > 0">
            {{ $t('categoryCard.objects', { n: category.numberAnnotations }) }}
          </p>
          <p v-else>{{ $t('categoryCard.noAnnotationsUseThisCategory') }}</p>
        </div>

        <div class="dropdown-menu" :aria-labelledby="'dropdownCategory' + category.id">
          <a class="dropdown-item" @click="onDeleteClick">{{ $t('categoryCard.delete') }}</a>
          <!--<a class="dropdown-item" @click="onDownloadClick"
            >{{ $t('categoryCard.downloadCocoImages') }}</a
          >-->
          <button
            class="dropdown-item"
            data-bs-toggle="modal"
            :data-bs-target="'#categoryEdit' + category.id"
          >{{ $t('categoryCard.edit') }}</button>
        </div>
      </div>

      <div
        v-show="$store.getters['user/loginEnabled']"
        class="card-footer text-muted"
      >{{ $t('common.createdBy', { name: category.creator }) }}</div>
    </div>

    <div class="modal fade" role="dialog" ref="category_settings"
        :id="'categoryEdit' + category.id" >
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('categoryCard.title', { name: category.name }) }}</h5>
            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
          </div>
          <div class="modal-body">
            <form>
              <div class="mb-3">
                <label>{{ $t('categoryCard.name') }}</label>
                <input
                  type="text"
                  :value="name"
                  required="true"
                  class="form-control"
                  :class="{'is-invalid': name.length === 0}"
                  @input="name = $event.target.value"
                />
              </div>

              <div class="mb-3">
                <label>{{ $t('categoryCard.supercategory') }}</label>
                <input
                  type="text"
                  class="form-control"
                  :value="category.supercategory"
                  @input="supercategory = $event.target.value"
                />
              </div>

              <div class="mb-3 row">
                <label class="col-sm-2 col-form-label">{{ $t('categoryCard.color') }}</label>
                <div class="col-sm-9">
                  <input v-model="color" type="color" class="form-control form-control-color w-100" />
                </div>
              </div>

              <div class="mb-3">
                <KeypointsDefinition
                  ref="keypoints"
                  v-model:value="keypoint"
                  element-id="keypoints"
                  :placeholder="$t('categoryCard.addAKeypoint')"
                ></KeypointsDefinition>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button
              type="button"
              class="btn btn-success"
              @click="onUpdateClick"
              :disabled="!isFormValid"
              :class="{ disabled: !isFormValid }"
              data-bs-dismiss="modal"
            >{{ $t('categoryCard.update') }}</button>
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ $t('categoryCard.close') }}</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { onModalHidden } from "@/libs/modal";
import axios from "axios";
import toastrs from "@/mixins/toastrs";
// import TagsInput from "@/components/TagsInput.vue";
import KeypointsDefinition from "@/components/KeypointsDefinition.vue";


export default {
  name: "CategoryCard",
  mixins: [toastrs],
  components: { KeypointsDefinition },
  data() {
    return {
      group: null,
      supercategory: this.category.supercategory,
      color: this.category.color,
      metadata: [],
      keypoint: {
        labels: [...this.category.keypoint_labels],
        edges: [...this.category.keypoint_edges],
        colors: [...this.category.keypoint_colors],
      },
      name: this.category.name,
      isMounted: false,
    };
  },
  props: {
    category: {
      type: Object,
      required: true
    }
  },
  computed: {
    isFormValid() {
      return (
        this.isMounted &&
        this.name.length !== 0 &&
        this.$refs &&
        this.$refs.keypoints &&
        this.$refs.keypoints.valid
      );
    }
  },
  created() {
    this.resetCategorySettings();
  },
  methods: {
    resetCategorySettings() {
      this.name = this.category.name;
      this.supercategory = this.category.supercategory;
      this.color = this.category.color;
      this.keypoint = {
        labels: [...this.category.keypoint_labels],
        edges: [...this.category.keypoint_edges],
        colors: [...this.category.keypoint_colors],
      };
    },
    onCardClick() {},
    onDownloadClick() {},
    onDeleteClick() {
      axios.delete("/api/category/" + this.category.id).then(() => {
        this.$parent.updatePage();
      });
    },
    onUpdateClick() {
      axios
        .put("/api/category/" + this.category.id, {
          name: this.name,
          color: this.color,
          supercategory: this.supercategory,
          metadata: this.metadata,
          keypoint_edges: this.keypoint.edges,
          keypoint_labels: this.keypoint.labels,
          keypoint_colors: this.keypoint.colors,
        })
        .then(() => {
          this.axiosReqestSuccess(
            "Updating Category",
            "Category successfully updated"
          );
          this.category.name = this.name;
          this.category.supercategory = this.supercategory;
          this.category.color = this.color;
          this.category.metadata = { ...this.metadata };
          this.category.keypoint_edges = [...this.keypoint.edges];
          this.category.keypoint_labels = [...this.keypoint.labels];
          this.category.keypoint_colors = [...this.keypoint.colors];
          this.$parent.updatePage();
        })
        .catch(error => {
          this.axiosReqestError(
            "Updating Category",
            error.response.data.message
          );
          this.$parent.updatePage();
        });
    }
  },
  mounted() {
    onModalHidden(this.$refs.category_settings, this.resetCategorySettings);
    this.isMounted = true;
  }
};
</script>

<style scoped>
.icon-more {
  width: 10%;
  margin: 3px 0;
  padding: 0;
  float: right;
  color: black;
}

.card-body {
  padding: 10px 10px 0 10px;
}

.color-icon {
  display: inline;
  margin: 0;
  padding-right: 10px;
}

.card-footer {
  padding: 2px;
  font-size: 11px;
}
</style>
