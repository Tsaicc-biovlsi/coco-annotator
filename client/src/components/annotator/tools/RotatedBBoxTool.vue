<script>
import paper from "paper";
import tool from "@/mixins/toolBar/tool";

/**
 * Rotated (oriented) bounding box tool.
 *
 *  - drag on empty canvas      draw a new box (at the last used angle if
 *                              "Keep last angle" is on, otherwise upright)
 *  - drag the round handle     rotate (hold Shift to snap)
 *  - drag a corner handle      resize, the opposite corner stays put
 *  - drag inside the box       move
 *
 * Boxes are stored as a 4-corner polygon in corner order, plus
 * annotation.isrbbox; the server derives rbbox = [cx, cy, w, h, angle].
 */
const HANDLE_SIZE = 7; // screen pixels
const ROTATE_OFFSET = 25; // screen pixels between box edge and rotate handle
const MIN_SIZE = 2; // screen pixels

function toRad(deg) {
  return (deg * Math.PI) / 180;
}

function normaliseAngle(angle) {
  angle = ((((angle + 180) % 360) + 360) % 360) - 180;
  return angle === -180 ? 180 : angle;
}

export default {
  name: "RotatedBBoxTool",
  mixins: [tool],
  props: {
    scale: {
      type: Number,
      default: 1
    }
  },
  data() {
    return {
      icon: "fa-rotate-right",
      name: "Rotated BBox",
      cursor: "crosshair",
      box: null, // { cx, cy, w, h, angle } in paper coordinates, angle in degrees
      overlay: null,
      drag: null,
      busy: false,
      lastAngle: 0,
      settings: {
        keepAngle: true,
        snap: 15,
        strokeColor: "#00e5ff"
      }
    };
  },
  computed: {
    isDisabled() {
      return this.$parent.current.annotation === -1;
    },
    annotationComponent() {
      return this.$parent.currentAnnotation;
    },
    boxInfo() {
      if (!this.box) return null;
      return {
        w: this.box.w.toFixed(1),
        h: this.box.h.toFixed(1),
        angle: this.box.angle.toFixed(1)
      };
    }
  },
  methods: {
    export() {
      return {
        keepAngle: this.settings.keepAngle,
        snap: this.settings.snap,
        strokeColor: this.settings.strokeColor
      };
    },
    setPreferences(pref) {
      if (pref.keepAngle != null) this.settings.keepAngle = pref.keepAngle;
      if (pref.snap != null) this.settings.snap = pref.snap;
      if (pref.strokeColor) this.settings.strokeColor = pref.strokeColor;
    },

    /* ---------- geometry ---------- */
    axes(angle) {
      let t = toRad(angle);
      let u = new paper.Point(Math.cos(t), Math.sin(t));
      let v = new paper.Point(-Math.sin(t), Math.cos(t));
      return { u, v };
    },
    corners(box) {
      let { u, v } = this.axes(box.angle);
      let c = new paper.Point(box.cx, box.cy);
      let hu = u.multiply(box.w / 2);
      let hv = v.multiply(box.h / 2);
      return [
        c.subtract(hu).subtract(hv),
        c.add(hu).subtract(hv),
        c.add(hu).add(hv),
        c.subtract(hu).add(hv)
      ];
    },
    boxFromCorners(points) {
      let [p0, p1, p2] = points;
      let center = points
        .reduce((acc, p) => acc.add(p), new paper.Point(0, 0))
        .divide(4);
      let edge = p1.subtract(p0);
      return {
        cx: center.x,
        cy: center.y,
        w: edge.length,
        h: p2.subtract(p1).length,
        angle: normaliseAngle((Math.atan2(edge.y, edge.x) * 180) / Math.PI)
      };
    },
    /** Box spanned by two opposite corners in the frame rotated by angle */
    boxFromDiagonal(a, b, angle) {
      let { u, v } = this.axes(angle);
      let d = b.subtract(a);
      let center = a.add(d.divide(2));
      return {
        cx: center.x,
        cy: center.y,
        w: Math.abs(d.dot(u)),
        h: Math.abs(d.dot(v)),
        angle
      };
    },
    toLocal(point, box) {
      let { u, v } = this.axes(box.angle);
      let d = point.subtract(new paper.Point(box.cx, box.cy));
      return { a: d.dot(u), b: d.dot(v) };
    },
    rotateHandlePosition(box) {
      let { v } = this.axes(box.angle);
      let c = new paper.Point(box.cx, box.cy);
      return c.subtract(v.multiply(box.h / 2 + ROTATE_OFFSET * this.scale));
    },

    /* ---------- overlay ---------- */
    clearOverlay() {
      if (this.overlay) this.overlay.remove();
      this.overlay = null;
    },
    drawOverlay() {
      this.clearOverlay();
      if (!this.box || !this.isActive) return;

      let corners = this.corners(this.box);
      let size = HANDLE_SIZE * this.scale;
      let stroke = this.settings.strokeColor;

      let outline = new paper.Path({
        segments: corners,
        closed: true,
        strokeColor: stroke,
        strokeWidth: 1.5 * this.scale,
        dashArray: [6 * this.scale, 4 * this.scale]
      });
      // mark the first edge so the box's heading is visible
      let heading = new paper.Path.Line({
        from: corners[0],
        to: corners[1],
        strokeColor: stroke,
        strokeWidth: 3 * this.scale
      });

      let top = corners[0].add(corners[1]).divide(2);
      let rotatePos = this.rotateHandlePosition(this.box);
      let stem = new paper.Path.Line({
        from: top,
        to: rotatePos,
        strokeColor: stroke,
        strokeWidth: 1 * this.scale
      });
      let rotate = new paper.Path.Circle({
        center: rotatePos,
        radius: size * 0.8,
        fillColor: stroke,
        strokeColor: "black",
        strokeWidth: 0.5 * this.scale
      });

      let handles = corners.map(
        p =>
          new paper.Path.Rectangle({
            point: p.subtract(size / 2),
            size: [size, size],
            fillColor: "white",
            strokeColor: "black",
            strokeWidth: 0.5 * this.scale
          })
      );

      this.overlay = new paper.Group([outline, heading, stem, rotate, ...handles]);
      this.overlay.locked = true; // never steal clicks from annotations
    },

    /* ---------- annotation sync ---------- */
    syncFromAnnotation() {
      if (this.drag) return;
      let annotation = this.annotationComponent;
      let corners = annotation ? annotation.getRotatedBoxCorners() : null;
      this.box = corners ? this.boxFromCorners(corners) : null;
      if (this.box) this.lastAngle = this.box.angle;
      this.drawOverlay();
    },
    annotationHasShape(annotation) {
      if (!annotation) return false;
      let path = annotation.compoundPath;
      return path != null && !path.isEmpty();
    },
    async commit(box, isNew) {
      let parent = this.$parent;
      let annotation = parent.currentAnnotation;

      // drawing a new box over an annotation that already has a shape
      // starts a new annotation (same behaviour as the BBox tool)
      if (isNew && this.annotationHasShape(annotation) && parent.currentCategory) {
        this.busy = true;
        try {
          await parent.currentCategory.createAnnotation();
        } finally {
          this.busy = false;
        }
        annotation = parent.currentAnnotation;
      }
      if (!annotation) return;

      annotation.setRotatedBox(this.corners(box));
      this.lastAngle = box.angle;
      this.box = box;
      this.drawOverlay();
    },

    /* ---------- mouse ---------- */
    hitTest(point) {
      if (!this.box) return null;
      let tol = HANDLE_SIZE * this.scale * 1.2;

      if (point.getDistance(this.rotateHandlePosition(this.box)) <= tol) {
        return { mode: "rotate" };
      }
      let corners = this.corners(this.box);
      for (let i = 0; i < 4; i++) {
        if (point.getDistance(corners[i]) <= tol) {
          return { mode: "resize", corner: i };
        }
      }
      let { a, b } = this.toLocal(point, this.box);
      if (Math.abs(a) <= this.box.w / 2 && Math.abs(b) <= this.box.h / 2) {
        return { mode: "move" };
      }
      return null;
    },
    onMouseDown(event) {
      if (this.busy) return;
      // the shape may have changed elsewhere (undo, other tools)
      this.syncFromAnnotation();
      let point = event.point;
      let hit = this.hitTest(point);

      if (hit) {
        let corners = this.corners(this.box);
        this.drag = {
          ...hit,
          start: point,
          startBox: { ...this.box },
          anchor: hit.mode === "resize" ? corners[(hit.corner + 2) % 4] : null
        };
        return;
      }

      let angle = this.settings.keepAngle ? this.lastAngle : 0;
      this.drag = { mode: "draw", start: point, angle };
      this.box = null;
      this.drawOverlay();
    },
    onMouseDrag(event) {
      if (!this.drag) return;
      let d = this.drag;
      let point = event.point;

      if (d.mode === "draw") {
        this.box = this.boxFromDiagonal(d.start, point, d.angle);
      } else if (d.mode === "move") {
        let delta = point.subtract(d.start);
        this.box = {
          ...d.startBox,
          cx: d.startBox.cx + delta.x,
          cy: d.startBox.cy + delta.y
        };
      } else if (d.mode === "resize") {
        this.box = this.boxFromDiagonal(d.anchor, point, d.startBox.angle);
      } else if (d.mode === "rotate") {
        let c = new paper.Point(d.startBox.cx, d.startBox.cy);
        let dir = point.subtract(c);
        let angle = (Math.atan2(dir.y, dir.x) * 180) / Math.PI + 90;
        if (event.modifiers.shift && this.settings.snap > 0) {
          angle = Math.round(angle / this.settings.snap) * this.settings.snap;
        }
        this.box = { ...d.startBox, angle: normaliseAngle(angle) };
      }
      this.drawOverlay();
    },
    onMouseUp() {
      if (!this.drag) return;
      let d = this.drag;
      this.drag = null;

      let min = MIN_SIZE * this.scale;
      if (!this.box || this.box.w < min || this.box.h < min) {
        // a click, not a drag: keep whatever is selected
        this.syncFromAnnotation();
        return;
      }
      this.commit(this.box, d.mode === "draw");
    },

    /* ---------- panel actions ---------- */
    rotateBy(degrees) {
      if (!this.box) return;
      this.commit({ ...this.box, angle: normaliseAngle(this.box.angle + degrees) }, false);
    },
    /** Rotate the corner order by 90° without moving the box (changes heading) */
    swapHeading() {
      if (!this.box) return;
      let b = this.box;
      this.commit({ ...b, w: b.h, h: b.w, angle: normaliseAngle(b.angle + 90) }, false);
    },
    deleteBox() {
      this.box = null;
      this.clearOverlay();
    }
  },
  watch: {
    isActive(active) {
      if (active) {
        this.tool.activate();
        localStorage.setItem("editorTool", this.name);
        this.syncFromAnnotation();
      } else {
        this.drag = null;
        this.clearOverlay();
      }
    },
    annotationComponent() {
      if (this.isActive) this.syncFromAnnotation();
    },
    "$parent.current.annotation"() {
      if (this.isActive) this.$nextTick(() => this.syncFromAnnotation());
    },
    scale() {
      this.drawOverlay();
    },
    "settings.strokeColor"() {
      this.drawOverlay();
    }
  },
  beforeUnmount() {
    this.clearOverlay();
  }
};
</script>
