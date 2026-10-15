<template>
  <div class="kp-def">
    <div class="kp-head">
      <span class="title">{{ title || $t('keypointsDefinition.title') }}</span>
      <span v-if="keypoints.length" class="text-muted small">{{ keypoints.length }}</span>
      <button type="button" class="btn btn-sm btn-outline-success ms-auto py-0" @click="addKeypoint">
        <i class="fa fa-plus" /> {{ $t('keypointsDefinition.add') }}
      </button>
    </div>
    <div v-if="keypoints.length" class="small text-muted mb-1">
      {{ keyTitle || $t('keypointsDefinition.label') }} → {{ valueTitle || $t('keypointsDefinition.connectsTo') }}
    </div>

    <div ref="grid" class="kp-grid">
      <div v-if="keypoints.length == 0" class="subtitle text-muted">
        <i>{{ $t('keypointsDefinition.noKeypoints') }}</i>
      </div>
      <div v-for="(object, index) in keypoints" :key="index" class="kp-row">
        <span class="kp-index">{{ index + 1 }}</span>
        <input
          :value="object.color"
          type="color"
          class="kp-color"
          :title="$t('keypointsDefinition.color')"
          @input="colorUpdated(index, $event.target.value)"
        />
        <input
          :value="object.label"
          type="text"
          class="form-control form-control-sm kp-label"
          :class="{ 'is-invalid': object.label_error.length !== 0 }"
          :title="object.label_error || ''"
          :required="object.edges.length !== 0"
          :placeholder="keyTitle || $t('keypointsDefinition.label')"
          @input="keypointLabelUpdated(index, $event.target.value)"
        />
        <TagsInput
          :value="object.edges"
          :placeholder="object.edges.length ? ' ' : $t('keypointsDefinition.addConnectedLabel')"
          class="kp-edges"
          :elementId="`index${index}`"
          :existing-tags="otherKeypointLabels(object.label)"
          :onlyExistingTags="true"
          :typeahead="true"
          :typeahead-activation-threshold="0"
          @update:value="keypointEdgesUpdated(index, $event)"
        ></TagsInput>
        <button
          type="button"
          class="btn btn-sm btn-link text-danger p-1 kp-remove"
          :title="$t('keypointsDefinition.remove')"
          :aria-label="$t('keypointsDefinition.remove')"
          @click="removeKeypoint(index)"
        >
          <i class="fa fa-trash" />
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import TagsInput from "@/components/TagsInput.vue";

const DISTINCT_COLORS = [
  "#bf5c4d",
  "#d99100",
  "#4d8068",
  "#0d2b80",
  "#9c73bf",
  "#ff1a38",
  "#bf3300",
  "#736322",
  "#33fff1",
  "#3369ff",
  "#9d13bf",
  "#733941",
  "#ffb499",
  "#d0d957",
  "#0b5e73",
  "#0000ff",
  "#730b5e",
  "#ff8533",
  "#518c0e",
  "#82c7d9",
  "#0000d9",
  "#ff1ab3",
  "#733c17",
  "#7cff4d",
  "#1ab3ff",
  "#0000cc",
  "#cc0052",
  "#cc9c66",
  "#8ae6a2",
  "#335280",
  "#0000bf",
  "#e673a1"
];

export default {
  name: "KeypointsDefinition",
  emits: ["initialized", "update:value", "rows"],
  components: { TagsInput },
  props: {
    value: {
      type: Object,
      required: true
    },
    title: {
      type: String,
      default: ""
    },
    keyTitle: {
      type: String,
      default: ""
    },
    valueTitle: {
      type: String,
      default: ""
    },
    exclude: {
      type: String,
      default: ""
    }
  },
  computed: {
    valid() {
      if (!this.isMounted) {
        return false;
      }
      for (let i = 0; i < this.keypoints.length; ++i) {
        if (this.keypoints[i].label_error.length !== 0) {
          return false;
        }
      }
      return true;
    }
  },
  data() {
    return {
      keypoints: [],
      hiddenValue: { edges: [], labels: [], colors: [] },
      isMounted: false,
      nextDistinct: -1,
    };
  },
  created() {
    this.keypoints = this.keypointsFromProp();
    this.$emit("initialized");
  },
  mounted() {
    this.isMounted = true;
  },
  methods: {
    export() {
      let keypoints = [];

      for (let i=0; i < this.value.labels.length; ++i) {
        keypoints.push({
          label: this.value.labels[i],
          edges: [],
          label_error: "",
          color: this.value.colors[i],
        });
      }
      this.value.edges.forEach(edge => {
        let label0 = edge[0] - 1;
        let label1 = edge[1] - 1;
        keypoints[label0].edges.push(this.value.labels[label1]);
        keypoints[label1].edges.push(this.value.labels[label0]);
      });

      return keypoints;
    },
    /** a keypoint goes, with every connection to it */
    removeKeypoint(index) {
      const gone = this.keypoints[index];
      // keypoints are stored by position: one taken from the middle shifts
      // the ones after it in shapes already annotated
      if (gone && gone.label && index < this.keypoints.length - 1 && !confirm(this.$t("keypointsDefinition.removeConfirm", { name: gone.label }))) {
        return;
      }
      this.keypoints.splice(index, 1);
      if (gone && gone.label) {
        this.keypoints.forEach(kp => {
          kp.edges = kp.edges.filter(e => e !== gone.label);
        });
      }
      this.hiddenValue = this.propFomKeypoints();
      this.$emit("update:value", this.hiddenValue);
    },
    /** a new keypoint, ready to type its name */
    addKeypoint() {
      this.createKeypoints();
      this.$nextTick(() => {
        const grid = this.$refs.grid;
        const inputs = grid ? grid.querySelectorAll(".kp-label") : [];
        const last = inputs[inputs.length - 1];
        if (last) {
          last.scrollIntoView({ block: "nearest" });
          last.focus();
        }
      });
    },
    createKeypoints() {
      this.keypoints.push({
        label: "",
        label_error: "",
        edges: [],
        color: this.nextDistinctColor(),
      });
    },
    keypointsFromProp() {
      let keypoints = [];
      if (
        this.value != null &&
        this.value.labels != null &&
        this.value.labels.length
      ) {
        for (let i=0; i < this.value.labels.length; ++i) {
          let label = this.value.labels[i];
          if (label.length > 0) {
            keypoints.push({
              label,
              label_error: "",
              edges: [],
              color: this.value.colors[i] || "#000",
            });
          }
        }

        this.value.edges.forEach(edge => {
          let label0 = edge[0] - 1;
          let label1 = edge[1] - 1;
          if (label0 < keypoints.length && label1 < keypoints.length) {
            keypoints[label0].edges.push(this.value.labels[label1]);
            keypoints[label1].edges.push(this.value.labels[label0]);
          }
        });
      }
      return keypoints;
    },
    colorUpdated(index, color) {
      this.keypoints[index].color = color;
      this.hiddenValue = this.propFomKeypoints();
      this.$emit("update:value", this.hiddenValue);
    },
    keypointLabelUpdated(index, label) {
      let current_kp = this.keypoints[index];
      let previous_label = current_kp.label;

      current_kp.label_error = "";
      if (label !== "") {
        for (let i = 0; i < this.keypoints.length; ++i) {
          if (i !== index) {
            let kp = this.keypoints[i];
            if (label === kp.label) {
              current_kp.label_error = this.$t("keypointsDefinition.duplicateLabel");
              kp.label_error = current_kp.label_error;
            } else if (
              previous_label === kp.label &&
              kp.label_error.length !== 0
            ) {
              kp.label_error = "";
            }
          }
        }
      } else if (current_kp.edges.length !== 0) {
        current_kp.label_error = this.$t("keypointsDefinition.labelRequired");
      }

      current_kp.label = label;
      if (current_kp.label_error === "") {
        if (label !== "") {
          for (let i = 0; i < this.keypoints.length; ++i) {
            if (i !== index) {
              let kp = this.keypoints[i];
              kp.edges = kp.edges.map(edge => {
                return edge === previous_label ? label : edge;
              });
            }
          }
        }
        this.hiddenValue = this.propFomKeypoints();
        this.$emit("update:value", this.hiddenValue);
      } else if (label !== "") {
        for (let i = 0; i < this.keypoints.length; ++i) {
          if (i !== index) {
            let kp = this.keypoints[i];
            kp.edges = kp.edges.filter(edge => {
              return edge != previous_label;
            });
          }
        }
      }
    },
    keypointEdgesUpdated(index, edges) {
      if (!Array.isArray(edges)) return;
      // the tags field hands over its own list (and keeps changing it): a copy
      edges = [...edges];
      const before = this.keypoints[index] ? this.keypoints[index].edges : [];
      if (before.length === edges.length && before.every((e, i) => e === edges[i])) return;
      let new_edges = new Set(edges);
      let current_kp = this.keypoints[index];
      // need to update the keypoints on the other end of the edges
      this.keypoints.forEach(kp => {
        if (kp.label !== current_kp.label) {
          // edges go both ways; sync other end
          let kp_edges = new Set(kp.edges);
          if (!new_edges.has(kp.label) && kp_edges.has(current_kp.label)) {
            kp_edges.delete(current_kp.label);
            kp.edges = Array.from(kp_edges);
          } else if (
            new_edges.has(kp.label) &&
            !kp_edges.has(current_kp.label)
          ) {
            kp_edges.add(current_kp.label);
            kp.edges = Array.from(kp_edges);
          }
          if (kp.edges.length === 0 && kp.label.length === 0 && kp.label_error) {
            kp.label_error = "";
          }
        }
      });

      this.keypoints[index].edges = edges;
      this.hiddenValue = this.propFomKeypoints();
      this.$emit("update:value", this.hiddenValue);
    },
    propFomKeypoints() {
      let edge_labels = {};
      let labels = [];
      let colors = [];
      this.keypoints.forEach(kp => {
        if (kp.label.length > 0) {
          labels.push(kp.label);
          colors.push(kp.color);
        }
      })
      this.keypoints.forEach(kp => {
        kp.edges.forEach(edge => {
          if (edge in edge_labels) {
            edge_labels[edge].add(kp.label);
          } else {
            edge_labels[kp.label] = edge_labels[kp.label] || new Set();
            edge_labels[kp.label].add(edge);
          }
        });
      });
      let edges = [];
      for (const label in edge_labels) {
        let label_index = labels.indexOf(label) + 1;
        edge_labels[label].forEach(edge => {
          let edge_index = labels.indexOf(edge) + 1;
          edges.push([label_index, edge_index]);
        });
      }
      return { labels, edges, colors };
    },
    otherKeypointLabels(current_label) {
      let labels = {};
      if (this.keypoints != null) {
        this.keypoints.forEach(keypoint => {
          if (keypoint.label !== "" && keypoint.label !== current_label) {
            labels[keypoint.label] = keypoint.label;
          }
        });
      }
      return labels;
    },
    clearKeypoints() {
      this.keypoints.splice(0, this.keypoints.length);
    },
    nextDistinctColor() {
      return DISTINCT_COLORS[++this.nextDistinct];
    }
  },
  watch: {
    // how many keypoints are listed (the dialog widens for several)
    "keypoints.length": {
      immediate: true,
      handler(n) {
        this.$emit("rows", n);
      }
    },
    value() {
      if (this.hiddenValue !== this.value) {
        this.hiddenValue = this.value;
        this.keypoints = this.keypointsFromProp();
      }
    }
  }
};
</script>

<style scoped>
.kp-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 2px;
}
/* several keypoints a row, so a long list fits without scrolling the page */
.kp-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 4px 16px;
  padding: 2px;
}
.kp-row {
  display: flex;
  align-items: flex-start;
  gap: 5px;
  min-width: 0;
}
.kp-index {
  flex: none;
  width: 1.6em;
  padding-top: 5px;
  text-align: right;
  font-size: 0.75rem;
  color: #868e96;
  font-variant-numeric: tabular-nums;
}
.kp-color {
  flex: none;
  width: 26px;
  height: 31px;
  padding: 2px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  background: #fff;
}
.kp-label {
  flex: none;
  width: 110px;
}
.kp-edges {
  flex: 1 1 auto;
  min-width: 0;
}
.kp-remove {
  flex: none;
}
/* the connections field: one line while it fits */
.kp-edges :deep(.tags-input) {
  padding: 2px 4px;
  min-height: 31px;
  row-gap: 2px;
}
.kp-edges :deep(.tags-input input[type="text"]) {
  min-width: 70px;
  font-size: 0.8rem;
  padding: 2px;
}
.kp-edges :deep(.tags-input-badge) {
  font-size: 0.72rem;
  margin: 1px 3px 1px 0;
}
</style>
