<script>
import tool from "@/mixins/toolBar/tool";

export default {
  name: "KeypointTool",
  mixins: [tool],
  props: {
    scale: {
      type: Number,
      default: 1
    },
    settings: {
      type: [Object, null],
      default: null
    }
  },
  data() {
    return {
      icon: "fa-map-marker",
      name: "Keypoints",
      cursor: "cell"
    };
  },
  methods: {
    export() {
      return {};
    },
    onMouseDown(event) {
      if (this.isDisabled) return;
      this.$parent.currentAnnotation.addKeypoint(event.point);
    }
  },
  computed: {
    /** Keypoints belong to an object: its box must be drawn first */
    hasBox() {
      let annotation = this.$parent.currentAnnotation;
      if (!annotation) return false;
      return !!(annotation.annotation.isbbox || annotation.annotation.isrbbox);
    },
    isDisabled() {
      if (this.$parent.current.annotation === -1) return true;
      return !this.hasBox;
    },
    tooltip() {
      if (this.$parent.current.annotation === -1) {
        return "Keypoints (select an annotation to activate tool)";
      }
      if (!this.hasBox) return "Keypoints (draw a BBox for this annotation first)";
      return "Keypoints Tool";
    }
  },
  watch: {},
  created() {},
  mounted() {}
};
</script>
