<template>
  <div class="metric-chart">
    <div class="d-flex align-items-baseline mb-1">
      <span class="fw-semibold small me-auto">{{ title }}</span>
      <span v-if="hover != null" class="small text-muted">epoch {{ xOf(hover) }}</span>
    </div>
    <svg
      :viewBox="`0 0 ${W} ${H}`"
      class="chart"
      role="img"
      :aria-label="title"
      @mousemove="onMove"
      @mouseleave="hover = null"
    >
      <!-- grid -->
      <g class="grid">
        <line v-for="t in yTicks" :key="'y' + t" :x1="PAD_L" :x2="W - PAD_R" :y1="y(t)" :y2="y(t)" />
      </g>
      <g class="axis">
        <text v-for="t in yTicks" :key="'yt' + t" :x="PAD_L - 4" :y="y(t) + 3" text-anchor="end">{{ fmt(t) }}</text>
        <text v-for="t in xTicks" :key="'xt' + t" :x="x(t)" :y="H - 4" text-anchor="middle">{{ t }}</text>
      </g>
      <polyline
        v-for="(s, i) in series"
        :key="s.key"
        :points="s.points"
        fill="none"
        :stroke="color(i)"
        stroke-width="2"
        stroke-linejoin="round"
        stroke-linecap="round"
      />
      <g v-if="hover != null">
        <line class="cursor" :x1="x(xOf(hover))" :x2="x(xOf(hover))" :y1="PAD_T" :y2="H - PAD_B" />
        <circle
          v-for="(s, i) in series"
          :key="'c' + s.key"
          :cx="x(xOf(hover))"
          :cy="y(value(hover, s.key))"
          r="3"
          :fill="color(i)"
        />
      </g>
    </svg>
    <div class="legend">
      <span v-for="(s, i) in series" :key="'l' + s.key" class="item">
        <span class="swatch" :style="{ background: color(i) }" />
        {{ short(s.key) }}
        <b>{{ fmt(value(hover != null ? hover : rows.length - 1, s.key)) }}</b>
      </span>
    </div>
  </div>
</template>

<script>
const PALETTE = ["#2a78d6", "#e8590c", "#1a9e6e", "#8a5cd1", "#d6336c", "#0f8fa8", "#a07c00", "#495057"];

/** Lines of some columns of per-epoch rows (Ultralytics results.csv). */
export default {
  name: "MetricChart",
  props: {
    rows: { type: Array, required: true },
    keys: { type: Array, required: true },
    title: { type: String, default: "" },
    // e.g. 1 for metrics between 0 and 1
    fixedMax: { type: Number, default: null }
  },
  data() {
    return { W: 460, H: 190, PAD_L: 38, PAD_R: 8, PAD_T: 8, PAD_B: 18, hover: null };
  },
  computed: {
    maxY() {
      if (this.fixedMax != null) return this.fixedMax;
      let m = 0;
      this.rows.forEach(r => this.keys.forEach(k => (m = Math.max(m, r[k] || 0))));
      return m > 0 ? m * 1.08 : 1;
    },
    maxX() {
      return Math.max(1, this.xOf(this.rows.length - 1));
    },
    series() {
      return this.keys.map(key => ({
        key,
        points: this.rows
          .map((r, i) => (r[key] == null ? null : `${this.x(this.xOf(i)).toFixed(1)},${this.y(r[key]).toFixed(1)}`))
          .filter(Boolean)
          .join(" ")
      }));
    },
    yTicks() {
      return [0, 0.25, 0.5, 0.75, 1].map(f => f * this.maxY);
    },
    xTicks() {
      const n = this.maxX;
      const step = Math.max(1, Math.ceil(n / 6));
      const out = [];
      for (let t = step; t <= n; t += step) out.push(t);
      if (!out.length || out[out.length - 1] !== n) out.push(n);
      return out;
    }
  },
  methods: {
    color(i) {
      return PALETTE[i % PALETTE.length];
    },
    xOf(i) {
      const r = this.rows[i];
      return r && r.epoch != null ? r.epoch : i + 1;
    },
    x(epoch) {
      const w = this.W - this.PAD_L - this.PAD_R;
      return this.PAD_L + (this.maxX <= 1 ? w : ((epoch - 1) / (this.maxX - 1)) * w);
    },
    y(v) {
      const h = this.H - this.PAD_T - this.PAD_B;
      return this.PAD_T + h - (Math.min(v || 0, this.maxY) / this.maxY) * h;
    },
    value(i, key) {
      const r = this.rows[i];
      return r ? r[key] : null;
    },
    fmt(v) {
      if (v == null) return "–";
      return Math.abs(v) >= 10 ? v.toFixed(1) : v.toFixed(3);
    },
    /** "metrics/mAP50-95(B)" -> "mAP50-95", "train/box_loss" -> "train box" */
    short(key) {
      return key.replace(/^metrics\//, "").replace(/\((B|M|P)\)$/, "").replace("_loss", "").replace("/", " ");
    },
    onMove(e) {
      const rect = e.currentTarget.getBoundingClientRect();
      const px = ((e.clientX - rect.left) / rect.width) * this.W;
      const w = this.W - this.PAD_L - this.PAD_R;
      const frac = Math.min(1, Math.max(0, (px - this.PAD_L) / w));
      this.hover = this.rows.length ? Math.round(frac * (this.rows.length - 1)) : null;
    }
  }
};
</script>

<style scoped>
.metric-chart {
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 8px 10px;
  background: #fff;
}
.chart {
  width: 100%;
  height: auto;
  display: block;
}
.grid line {
  stroke: #eef0f3;
}
.axis text {
  font-size: 9px;
  fill: #868e96;
}
.cursor {
  stroke: #adb5bd;
  stroke-dasharray: 3 3;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 2px 12px;
  font-size: 0.75rem;
  color: #495057;
}
.legend .item {
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}
.swatch {
  display: inline-block;
  width: 10px;
  height: 3px;
  border-radius: 2px;
  vertical-align: middle;
  margin-right: 3px;
}
</style>
