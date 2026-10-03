import paper from "paper";
import { renderToolIcon } from "./render";

export default {
  emits: ["setcursor", "update:selected"],
  props: {
    selected: {
      type: String,
      required: true
    }
  },
  render() {
    return renderToolIcon(this, this.tooltip);
  },
  data() {
    return {
      tool: null,
      enabled: false,
      cursor: "default",
      // Named iconColors (not color): Vue 3 merges mixin data shallowly, and
      // several tools have their own `color` settings object.
      iconColors: {
        enabled: "white",
        active: "#2ecc71",
        disabled: "gray",
        toggle: "red"
      }
    };
  },
  methods: {
    onMouseMove() {},
    onMouseDown() {},
    onMouseDrag() {},
    onMouseUp() {},
    click() {
      this.update();
    },
    update() {
      if (this.isDisabled) return;

      this.$emit("update:selected", this.name);
    },
    setPreferences() {}
  },
  computed: {
    isActive() {
      if (this.selected == this.name) {
        this.$emit("setcursor", this.cursor);
        return true;
      }
      return false;
    },
    iconColor() {
      if (this.isDisabled) return this.iconColors.disabled;

      if (this.isToggled) return this.iconColors.toggle;
      if (this.isActive) return this.iconColors.active;

      return this.iconColors.enabled;
    },
    isDisabled() {
      return false;
    },
    tooltip() {
      if (this.isDisabled) {
        return this.name + " (select an annotation to activate tool)";
      }
      return this.name + " Tool";
    }
  },
  watch: {
    isActive(active) {
      if (active) {
        this.tool.activate();
      }
    },
    isDisabled(disabled) {
      if (disabled && this.isActive) {
        this.$emit("update:selected", "Select");
      }
    }
  },
  mounted() {
    this.tool = new paper.Tool();

    this.tool.onMouseDown = this.onMouseDown;
    this.tool.onMouseDrag = this.onMouseDrag;
    this.tool.onMouseMove = this.onMouseMove;
    this.tool.onMouseUp = this.onMouseUp;
  }
};
