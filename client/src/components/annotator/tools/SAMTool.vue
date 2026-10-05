<script>
import paper from "paper";
import axios from "axios";
import tool from "@/mixins/toolBar/tool";

/**
 * Segment Anything (SAM) assisted segmentation.
 *
 *  - click            add a point on the object
 *  - Shift + click    add a point on the background (exclude it)
 *  - drag             draw a box around the object
 *  - Enter / Apply    add the preview to the current annotation
 *
 * The server caches the image embedding, so every click after the first
 * only runs SAM's light-weight mask decoder.
 */
const DRAG_THRESHOLD = 4; // screen pixels

export default {
  name: "SAMTool",
  mixins: [tool],
  props: {
    scale: {
      type: Number,
      default: 1
    }
  },
  data() {
    return {
      icon: "fa-bullseye",
      name: "SAM",
      cursor: "crosshair",
      status: {
        checked: false,
        available: false,
        preparing: false,
        predicting: false,
        message: ""
      },
      points: [], // { point: paper.Point, label: 0|1 }
      box: null, // [paper.Point, paper.Point]
      score: null,
      preview: null,
      markers: null,
      dragStart: null,
      boxPath: null,
      requestId: 0,
      settings: {
        replace: false
      }
    };
  },
  computed: {
    isDisabled() {
      return !this.status.available || this.$parent.current.annotation === -1;
    },
    tooltip() {
      if (this.status.checked && !this.status.available) {
        return this.$t("sam.unavailableTooltip");
      }
      if (this.isDisabled) return this.$t("toolbar.needsAnnotation", { tool: "SAM" });
      return this.$t("sam.tooltip");
    },
    hasPrompt() {
      return this.points.length > 0 || this.box != null;
    },
    statusText() {
      if (!this.status.checked) return this.$t("sam.checking");
      if (!this.status.available) return this.status.message || this.$t("sam.unavailable");
      if (this.status.preparing) return this.$t("sam.preparing");
      if (this.status.predicting) return this.$t("sam.segmenting");
      if (this.preview) return this.$t("sam.score", { score: Math.max(0, this.score * 100).toFixed(0) });
      return this.status.model ? `${this.status.model} · ${this.$t("sam.hint")}` : this.$t("sam.hint");
    },
    imageId() {
      return this.$parent.image.id;
    }
  },
  methods: {
    export() {
      return { replace: this.settings.replace };
    },
    setPreferences(pref) {
      if (pref.replace != null) this.settings.replace = pref.replace;
    },
    checkStatus() {
      axios
        .get("/api/model/")
        .then(response => {
          let sam = response.data.sam || {};
          this.status.available = !!sam.available;
          this.status.model = sam.model_type || "";
          this.status.message = sam.error || "";
        })
        .catch(() => {
          this.status.available = false;
        })
        .finally(() => (this.status.checked = true));
    },
    prepare() {
      if (!this.status.available || this.imageId == null) return;
      this.status.preparing = true;
      axios
        .post(`/api/model/sam/${this.imageId}/prepare`)
        .catch(() => {})
        .finally(() => (this.status.preparing = false));
    },

    /* ---------- coordinates ---------- */
    toImage(point) {
      let raster = this.$parent.image.raster;
      return [
        Math.round(point.x + raster.width / 2),
        Math.round(point.y + raster.height / 2)
      ];
    },

    /* ---------- drawing ---------- */
    drawMarkers() {
      if (this.markers) this.markers.remove();
      this.markers = null;
      if (!this.isActive) return;

      let r = 5 * this.scale;
      let items = this.points.map(
        p =>
          new paper.Path.Circle({
            center: p.point,
            radius: r,
            fillColor: p.label ? "#2ecc71" : "#e74c3c",
            strokeColor: "white",
            strokeWidth: 1.5 * this.scale
          })
      );
      if (this.box) {
        items.push(
          new paper.Path.Rectangle({
            from: this.box[0],
            to: this.box[1],
            strokeColor: "#f1c40f",
            strokeWidth: 1.5 * this.scale,
            dashArray: [6 * this.scale, 4 * this.scale]
          })
        );
      }
      this.markers = new paper.Group(items);
      this.markers.locked = true;
    },
    clearPreview() {
      if (this.preview) this.preview.remove();
      this.preview = null;
      this.score = null;
    },
    showPreview(segmentation) {
      this.clearPreview();
      if (!segmentation || segmentation.length === 0) return;

      let raster = this.$parent.image.raster;
      let center = new paper.Point(raster.width / 2, raster.height / 2);
      let compound = new paper.CompoundPath();
      segmentation.forEach(polygon => {
        let path = new paper.Path();
        for (let j = 0; j < polygon.length; j += 2) {
          path.add(new paper.Point(polygon[j], polygon[j + 1]).subtract(center));
        }
        path.closePath();
        compound.addChild(path);
      });

      let annotation = this.$parent.currentAnnotation;
      compound.fillColor = annotation ? annotation.color : "#3498db";
      compound.opacity = 0.45;
      compound.strokeColor = "white";
      compound.strokeWidth = 1.5 * this.scale;
      compound.dashArray = [4 * this.scale, 3 * this.scale];
      compound.locked = true;
      this.preview = compound;
      if (this.markers) this.markers.bringToFront();
    },

    /* ---------- prediction ---------- */
    predict() {
      if (!this.hasPrompt) {
        this.clearPreview();
        return;
      }
      let body = {
        points: this.points.map(p => this.toImage(p.point)),
        labels: this.points.map(p => p.label)
      };
      if (this.box) {
        let [a, b] = this.box.map(this.toImage);
        body.box = [
          Math.min(a[0], b[0]),
          Math.min(a[1], b[1]),
          Math.max(a[0], b[0]),
          Math.max(a[1], b[1])
        ];
      }

      let id = ++this.requestId;
      this.status.predicting = true;
      axios
        .post(`/api/model/sam/${this.imageId}`, body)
        .then(response => {
          if (id !== this.requestId) return; // a newer prompt is on its way
          this.showPreview(response.data.segmentation);
          this.score = response.data.score;
        })
        .catch(error => {
          if (id !== this.requestId) return;
          let message =
            (error.response && error.response.data && error.response.data.message) ||
            this.$t("sam.requestFailed");
          this.$toastr.error(message, "SAM", { positionClass: "toast-bottom-left" });
        })
        .finally(() => {
          if (id === this.requestId) this.status.predicting = false;
        });
    },
    apply() {
      let annotation = this.$parent.currentAnnotation;
      if (!this.preview || !annotation) return;

      let shape = this.preview.clone();
      shape.locked = false;
      if (this.settings.replace && annotation.compoundPath) {
        annotation.subtract(annotation.compoundPath.clone(), false, true);
        annotation.unite(shape, true, false);
      } else {
        annotation.unite(shape, true, true);
      }
      shape.remove();
      this.reset();
    },
    undoPoint() {
      if (this.points.length > 0) this.points.pop();
      else this.box = null;
      this.drawMarkers();
      this.predict();
    },
    reset() {
      this.requestId++;
      this.points = [];
      this.box = null;
      this.status.predicting = false;
      this.clearPreview();
      this.drawMarkers();
    },

    /* ---------- mouse & keyboard ---------- */
    onMouseDown(event) {
      this.dragStart = event.point;
    },
    onMouseDrag(event) {
      if (!this.dragStart) return;
      if (event.point.getDistance(this.dragStart) < DRAG_THRESHOLD * this.scale) return;
      if (this.boxPath) this.boxPath.remove();
      this.boxPath = new paper.Path.Rectangle({
        from: this.dragStart,
        to: event.point,
        strokeColor: "#f1c40f",
        strokeWidth: 1.5 * this.scale
      });
      this.boxPath.locked = true;
    },
    onMouseUp(event) {
      if (!this.dragStart) return;
      let start = this.dragStart;
      this.dragStart = null;
      if (this.boxPath) {
        this.boxPath.remove();
        this.boxPath = null;
      }

      if (event.point.getDistance(start) >= DRAG_THRESHOLD * this.scale) {
        this.box = [start, event.point];
      } else {
        this.points.push({ point: event.point, label: event.modifiers.shift ? 0 : 1 });
      }
      this.drawMarkers();
      this.predict();
    },
    onKeyDown(e) {
      if (!this.isActive) return;
      let tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "Enter" && this.preview) {
        e.preventDefault();
        this.apply();
      }
    }
  },
  watch: {
    isActive(active) {
      if (active) {
        this.tool.activate();
        localStorage.setItem("editorTool", this.name);
        this.prepare();
      } else {
        this.reset();
      }
    },
    "$parent.current.annotation"() {
      this.reset();
    },
    scale() {
      this.drawMarkers();
    }
  },
  mounted() {
    this.checkStatus();
    window.addEventListener("keydown", this.onKeyDown);
  },
  beforeUnmount() {
    window.removeEventListener("keydown", this.onKeyDown);
    this.reset();
  }
};
</script>
