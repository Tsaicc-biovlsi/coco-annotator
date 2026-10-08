<template>
  <div class="quick-review">
    <div style="padding-top: 55px" />
    <div class="qr-bar d-flex flex-wrap align-items-center gap-2">
      <RouterLink :to="`/dataset/${datasetId}`" class="btn btn-sm btn-outline-light" :title="$t('quickReview.back')">
        <i class="fa fa-arrow-left" />
      </RouterLink>
      <div class="me-2">
        <div class="fw-semibold">{{ $t('quickReview.title') }}</div>
        <div class="small text-white-50">{{ datasetName }}</div>
      </div>

      <div class="btn-group btn-group-sm" role="group" :aria-label="$t('quickReview.layout')">
        <button
          v-for="n in GRIDS"
          :key="n"
          type="button"
          class="btn"
          :class="grid === n ? 'btn-light' : 'btn-outline-light'"
          :title="n === 1 ? $t('quickReview.single') : $t('quickReview.gridN', { n: n * n })"
          @click="setGrid(n)"
        >
          <i v-if="n === 1" class="fa fa-square-o" />
          <span v-else>{{ n }}×{{ n }}</span>
        </button>
      </div>

      <select v-model="status" class="form-select form-select-sm w-auto" :aria-label="$t('quickReview.show')">
        <option value="labeled">{{ $t('review.status.labeled') }}</option>
        <option value="rejected">{{ $t('review.status.rejected') }}</option>
        <option value="approved">{{ $t('review.status.approved') }}</option>
        <option value="all">{{ $t('review.all') }}</option>
      </select>
      <select v-model="order" class="form-select form-select-sm w-auto" :aria-label="$t('quickReview.order')">
        <option value="file_name">{{ $t('quickReview.byFileName') }}</option>
        <option value="submitted">{{ $t('quickReview.bySubmitted') }}</option>
      </select>
      <select v-model="labeler" class="form-select form-select-sm w-auto" :aria-label="$t('quickReview.by')">
        <option value="">{{ $t('quickReview.anyone') }}</option>
        <option v-for="u in labelers" :key="u" :value="u">{{ u }}</option>
      </select>

      <div class="form-check form-switch m-0 text-white-50 small" :title="$t('quickReview.syncHint')">
        <input id="qrSync" v-model="syncZoom" type="checkbox" class="form-check-input" role="switch" />
        <label class="form-check-label" for="qrSync">{{ $t('quickReview.syncZoom') }}</label>
      </div>
      <div class="form-check form-switch m-0 text-white-50 small">
        <input id="qrShow" v-model="showShapes" type="checkbox" class="form-check-input" role="switch" />
        <label class="form-check-label" for="qrShow">{{ $t('quickReview.showShapes') }} (H)</label>
      </div>
      <div class="form-check form-switch m-0 text-white-50 small" :title="$t('quickReview.showNamesHint')">
        <input id="qrNames" v-model="showNames" type="checkbox" class="form-check-input" role="switch" :disabled="!showShapes" />
        <label class="form-check-label" for="qrNames">{{ $t('quickReview.showNames') }} (L)</label>
      </div>

      <span v-if="soloCat != null" class="solo-tag">
        <i class="dot" :style="{ background: (categories[soloCat] && categories[soloCat].color) || '#00e5ff' }" />
        {{ $t('quickReview.onlyCat', { name: catLabel(soloCat) }) }}
        <button type="button" class="btn-close btn-close-white" :aria-label="$t('quickReview.soloOff')" @click="soloCat = null" />
      </span>

      <div class="ms-auto d-flex align-items-center gap-2">
        <span class="small text-white-50">
          {{ total ? $t('quickReview.range', { from: (page - 1) * perPage + 1, to: Math.min(page * perPage, total), n: total }) : '' }}
        </span>
        <button type="button" class="btn btn-sm btn-outline-light" :disabled="page <= 1 || loading" @click="go(page - 1)">
          <i class="fa fa-chevron-left" />
        </button>
        <button type="button" class="btn btn-sm btn-outline-light" :disabled="page >= pages || loading" @click="go(page + 1)">
          <i class="fa fa-chevron-right" />
        </button>
        <button
          v-if="canReview && grid > 1"
          type="button"
          class="btn btn-sm btn-success"
          :disabled="!pending.length || busy"
          :title="'Shift+Y'"
          @click="approveAll"
        >
          <i class="fa fa-check-square-o" /> {{ $t('quickReview.approvePage', { n: pending.length }) }}
        </button>
      </div>
    </div>

    <div v-if="!loading && !images.length" class="qr-empty text-center text-white-50">
      <i class="fa fa-check-circle-o fa-4x d-block mb-3" />
      {{ status === 'labeled' ? $t('quickReview.allDone') : $t('exportCategories.noMatch') }}
      <div class="mt-3">
        <RouterLink :to="`/dataset/${datasetId}`" class="btn btn-sm btn-outline-light">{{ $t('quickReview.back') }}</RouterLink>
      </div>
    </div>

    <div v-else class="qr-grid" :style="{ gridTemplateColumns: `repeat(${grid}, 1fr)`, gridTemplateRows: `repeat(${Math.max(1, Math.min(grid, Math.ceil(images.length / grid)))}, 1fr)` }">
      <div
        v-for="(img, i) in images"
        :key="img.id"
        class="tile"
        :class="{ focus: i === focus, done: !!decided[img.id] }"
        @click="onTileClick(i)"
        @dblclick="openImage(img)"
      >
        <svg
          class="pic"
          :class="{ zoomed: isZoomed(img) }"
          :viewBox="viewBox(img)"
          preserveAspectRatio="xMidYMid meet"
          @wheel.prevent="onWheel($event, img)"
          @mousedown="onPanStart($event, img)"
          @mouseleave="hover = null"
        >
          <image :href="imageUrl(img)" x="0" y="0" :width="img.width" :height="img.height" />
          <g v-if="showShapes">
            <g
              v-for="a in img.annotations"
              :key="a.id"
              :class="{ dim: isDim(img, a.category_id), lit: isLit(img, a.category_id) }"
              @mouseenter="hover = { cat: a.category_id, all: true }"
              @mouseleave="hover = null"
            >
              <title>{{ catLabel(a.category_id) }}</title>
              <polygon
                v-for="(ring, k) in a.segmentation"
                :key="k"
                :points="points(ring)"
                :fill="colorOf(a)"
                fill-opacity="0.28"
                :stroke="colorOf(a)"
                stroke-width="2"
                vector-effect="non-scaling-stroke"
              />
              <template v-for="(p, k) in keypoints(a)" :key="'k' + k">
                <circle :cx="p[0]" :cy="p[1]" :r="Math.max(img.width, img.height) / 250" :fill="colorOf(a)" stroke="#fff" stroke-width="1" vector-effect="non-scaling-stroke" />
              </template>
            </g>
            <!-- category names, a fixed size on screen whatever the zoom -->
            <g v-if="showNames" class="names" pointer-events="none">
              <text
                v-for="l in nameLabels(img)"
                :key="l.id"
                :x="l.x"
                :y="l.y"
                :font-size="l.size"
                :stroke-width="l.size / 4"
                :fill="l.color"
                :class="{ dim: isDim(img, l.cat) }"
              >{{ l.text }}</text>
            </g>
          </g>
        </svg>

        <div v-if="showShapes && showNames && img.annotations.length" class="legend" @click.stop @dblclick.stop>
          <span
            v-for="c in catCounts(img)"
            :key="c.id"
            class="chip"
            :class="{ off: isDim(img, c.id), on: soloCat === c.id }"
            :title="catLabel(c.id) + ' — ' + $t(soloCat === c.id ? 'quickReview.soloOff' : 'quickReview.soloOn')"
            @mouseenter="hover = { cat: c.id, all: true }"
            @mouseleave="hover = null"
            @click.stop="toggleSolo(c.id)"
          >
            <i class="dot" :style="{ background: c.color }" />{{ c.name }}<b>{{ c.n }}</b>
          </span>
        </div>

        <div v-if="decided[img.id]" class="stamp" :class="decided[img.id]">
          <i class="fa" :class="decided[img.id] === 'approved' ? 'fa-check' : 'fa-undo'" />
          {{ $t('review.status.' + decided[img.id]) }}
        </div>

        <div class="tile-foot d-flex align-items-center gap-2">
          <span class="badge" :class="statusClass(decided[img.id] || img.status)">{{ $t('review.status.' + (decided[img.id] || img.status)) }}</span>
          <div class="min-w-0 flex-grow-1">
            <div class="fname text-truncate" :title="img.file_name">{{ img.file_name }}</div>
            <div class="meta text-truncate">
              <span v-if="img.labeled_by"><i class="fa fa-user-o" /> {{ img.labeled_by }}</span>
              <span>{{ $t('quickReview.nShapes', { n: img.annotations.length }) }}</span>
              <span v-if="img.review_note" class="text-warning" :title="img.review_note"><i class="fa fa-comment-o" /> {{ img.review_note }}</span>
            </div>
          </div>
          <template v-if="rejecting === img.id">
            <input
              :ref="el => (noteInput = el)"
              v-model="note"
              class="form-control form-control-sm note"
              :placeholder="$t('review.notePlaceholder')"
              @keydown.enter.stop.prevent="act(img, 'reject')"
              @keydown.esc.stop.prevent="rejecting = null"
              @click.stop
            />
            <button type="button" class="btn btn-sm btn-danger" :disabled="busy" @click.stop="act(img, 'reject')">
              <i class="fa fa-undo" />
            </button>
          </template>
          <template v-else-if="canReview">
            <button
              type="button"
              class="btn btn-sm btn-success"
              :disabled="busy || decided[img.id] === 'approved'"
              :title="$t('review.approve') + ' (Y)'"
              @click.stop="act(img, 'approve')"
            ><i class="fa fa-check" /></button>
            <button
              type="button"
              class="btn btn-sm btn-outline-danger"
              :disabled="busy || decided[img.id] === 'rejected'"
              :title="$t('review.reject') + ' (X)'"
              @click.stop="startReject(img)"
            ><i class="fa fa-undo" /></button>
          </template>
          <button type="button" class="btn btn-sm btn-outline-light" :title="$t('quickReview.open') + ' (Enter)'" @click.stop="openImage(img)">
            <i class="fa fa-pencil" />
          </button>
        </div>
      </div>
    </div>

    <div class="qr-help small text-white-50">
      {{ $t('quickReview.keys') }}
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { statusClass } from "@/components/annotator/ReviewBar.vue";
import { modalOpen } from "@/libs/modal";
import { pathLabel } from "@/libs/parents";

const GRIDS = [1, 2, 3, 4];
const GRID_KEY = "review/quickGrid";

function readGrid() {
  try {
    const n = parseInt(localStorage.getItem(GRID_KEY), 10);
    return GRIDS.includes(n) ? n : 3;
  } catch {
    return 3;
  }
}

/**
 * Quick review: one or several images at a time with their annotations drawn,
 * approve / reject each (or the whole page) without opening the annotator.
 */
export default {
  name: "Review",
  props: { identifier: { type: [String, Number], required: true } },
  data() {
    return {
      GRIDS,
      grid: readGrid(),
      status: this.$route.query.status || "labeled",
      labeler: "",
      order: (() => { try { return localStorage.getItem("review/quickOrder") || "file_name"; } catch { return "file_name"; } })(),
      showShapes: true,
      // category names on the shapes and a per-image list of categories
      showNames: (() => { try { return localStorage.getItem("review/showNames") !== "false"; } catch { return true; } })(),
      // a category hovered (a shape or the category list): lit in every image
      hover: null,
      // a category clicked in a list: only that one shows in every image
      soloCat: null,
      // the size of one picture on screen, for names that keep their size
      picPx: { w: 400, h: 300 },
      images: [],
      categories: {},
      labelers: [],
      canReview: false,
      datasetName: "",
      total: 0,
      page: 1,
      pages: 1,
      loading: false,
      busy: false,
      focus: 0,
      decided: {},
      views: {},
      // zoom / move every image on the page together (Shift does the other)
      syncZoom: (() => { try { return localStorage.getItem("review/syncZoom") !== "false"; } catch { return true; } })(),
      panMoved: false,
      rejecting: null,
      note: "",
      noteInput: null
    };
  },
  computed: {
    datasetId() {
      return parseInt(this.identifier, 10);
    },
    perPage() {
      return this.grid * this.grid;
    },
    pending() {
      return this.images.filter(i => !this.decided[i.id] && i.status !== "approved");
    }
  },
  watch: {
    status() { this.go(1); },
    labeler() { this.go(1); },
    showNames(value) {
      try {
        localStorage.setItem("review/showNames", String(value));
      } catch {
        // not remembered
      }
    },
    grid() {
      this.$nextTick(this.measure);
    },
    syncZoom(value) {
      try {
        localStorage.setItem("review/syncZoom", String(value));
      } catch {
        // not remembered
      }
    },
    order(value) {
      try {
        localStorage.setItem("review/quickOrder", value);
      } catch {
        // not remembered
      }
      this.go(1);
    }
  },
  methods: {
    statusClass,
    setGrid(n) {
      // keep the first image of the current page in view
      const first = (this.page - 1) * this.perPage;
      this.grid = n;
      try {
        localStorage.setItem(GRID_KEY, String(n));
      } catch {
        // not remembered
      }
      this.go(Math.floor(first / (n * n)) + 1);
    },
    /* ---------- zoom (wheel, at the cursor) and pan (drag) per image ---------- */
    viewOf(img) {
      return this.views[img.id] || { x: 0, y: 0, w: img.width, h: img.height };
    },
    viewBox(img) {
      const v = this.viewOf(img);
      return `${v.x} ${v.y} ${v.w} ${v.h}`;
    },
    isZoomed(img) {
      return !!this.views[img.id];
    },
    /** screen point -> image coordinates (the svg letterboxes the image) */
    toImage(svg, clientX, clientY) {
      const pt = svg.createSVGPoint();
      pt.x = clientX;
      pt.y = clientY;
      return pt.matrixTransform(svg.getScreenCTM().inverse());
    },
    setView(img, v) {
      // fully out: back to the whole image
      if (v.w >= img.width && v.h >= img.height) {
        const views = { ...this.views };
        delete views[img.id];
        this.views = views;
        return;
      }
      // keep inside the image
      v.w = Math.min(v.w, img.width);
      v.h = Math.min(v.h, img.height);
      v.x = Math.min(Math.max(0, v.x), img.width - v.w);
      v.y = Math.min(Math.max(0, v.y), img.height - v.h);
      this.views = { ...this.views, [img.id]: v };
    },
    zoomAt(img, svg, clientX, clientY, factor) {
      const p = this.toImage(svg, clientX, clientY);
      const v = this.viewOf(img);
      const minSize = Math.max(16, Math.min(img.width, img.height) / 40);
      let w = v.w * factor, h = v.h * factor;
      if (w < minSize || h < minSize) return;
      // the point under the cursor stays under the cursor
      this.setView(img, { x: p.x - (p.x - v.x) * factor, y: p.y - (p.y - v.y) * factor, w, h });
    },
    onWheel(e, img) {
      const factor = Math.exp((e.deltaY > 0 ? 1 : -1) * Math.min(Math.abs(e.deltaY), 120) / 600);
      if (this.syncZoom !== e.shiftKey) {
        // every image on the page zooms to the same place (Shift: the other way round)
        const svg = e.currentTarget;
        const p = this.toImage(svg, e.clientX, e.clientY);
        this.images.forEach(other => {
          const v = this.viewOf(other);
          const sx = other.width / img.width, sy = other.height / img.height;
          const ox = p.x * sx, oy = p.y * sy;
          this.setView(other, { x: ox - (ox - v.x) * factor, y: oy - (oy - v.y) * factor, w: v.w * factor, h: v.h * factor });
        });
        return;
      }
      this.focus = this.images.indexOf(img);
      this.zoomAt(img, e.currentTarget, e.clientX, e.clientY, factor);
    },
    onPanStart(e, img) {
      if (e.button !== 0 || !this.isZoomed(img)) return;
      const svg = e.currentTarget;
      const start = this.toImage(svg, e.clientX, e.clientY);
      const together = this.syncZoom !== e.shiftKey;
      const others = together ? this.images.filter(o => this.isZoomed(o)) : [img];
      const starts = Object.fromEntries(others.map(o => [o.id, { ...this.viewOf(o) }]));
      this.panMoved = false;
      const move = ev => {
        // move the view so the grabbed point follows the mouse (the others the same share)
        const ctm = svg.getScreenCTM();
        const dx = (ev.clientX - e.clientX) / ctm.a, dy = (ev.clientY - e.clientY) / ctm.d;
        if (Math.abs(ev.clientX - e.clientX) + Math.abs(ev.clientY - e.clientY) > 3) this.panMoved = true;
        others.forEach(o => {
          const v0 = starts[o.id];
          const sx = o.width / img.width, sy = o.height / img.height;
          this.setView(o, { ...v0, x: v0.x - dx * sx, y: v0.y - dy * sy });
        });
      };
      const up = () => {
        window.removeEventListener("mousemove", move);
        window.removeEventListener("mouseup", up);
      };
      window.addEventListener("mousemove", move);
      window.addEventListener("mouseup", up);
      void start;
    },
    onTileClick(i) {
      // the end of a drag is not a click
      if (this.panMoved) {
        this.panMoved = false;
        return;
      }
      this.focus = i;
    },
    resetZoom() {
      this.views = {};
    },
    imageUrl(img) {
      // the whole file for one image or a zoomed one; smaller copies for a grid
      if (this.grid === 1 || (this.views[img.id] && this.views[img.id].w < img.width * 0.7)) return `/api/image/${img.id}`;
      const width = { 2: 1000, 3: 700, 4: 520 }[this.grid] || 700;
      return `/api/image/${img.id}?width=${Math.min(width, img.width)}`;
    },
    points(ring) {
      const out = [];
      for (let i = 0; i + 1 < ring.length; i += 2) out.push(`${ring[i]},${ring[i + 1]}`);
      return out.join(" ");
    },
    keypoints(a) {
      const k = a.keypoints || [];
      const out = [];
      for (let i = 0; i + 2 < k.length; i += 3) if (k[i + 2] > 0) out.push([k[i], k[i + 1]]);
      return out;
    },
    /** the category to show alone in this image, or null for all */
    focusCat(img) {
      if (this.hover && (this.hover.all || this.hover.img === img.id)) return this.hover.cat;
      return this.soloCat;
    },
    isDim(img, cat) {
      const f = this.focusCat(img);
      return f != null && f !== cat;
    },
    isLit(img, cat) {
      const f = this.focusCat(img);
      return f != null && f === cat;
    },
    toggleSolo(cat) {
      this.soloCat = this.soloCat === cat ? null : cat;
      this.hover = null;
    },
    catLabel(id) {
      const c = this.categories[id];
      if (!c) return this.$t("quickReview.noCategory");
      const parent = (c.parents || [])[0];
      return parent ? `${pathLabel(parent)} › ${c.name}` : c.name;
    },
    /** categories used on one image, most used first */
    catCounts(img) {
      const counts = {};
      img.annotations.forEach(a => (counts[a.category_id] = (counts[a.category_id] || 0) + 1));
      return Object.entries(counts)
        .map(([id, n]) => {
          const c = this.categories[id];
          return { id: Number(id), n, name: c ? c.name : this.$t("quickReview.noCategory"), color: (c && c.color) || "#00e5ff" };
        })
        .sort((a, b) => b.n - a.n || a.name.localeCompare(b.name));
    },
    measure() {
      const svg = this.$el && this.$el.querySelector && this.$el.querySelector(".pic");
      if (svg && svg.clientWidth) this.picPx = { w: svg.clientWidth, h: svg.clientHeight };
    },
    /** the top-left corner of a shape, in image coordinates */
    corner(a) {
      let x = Infinity, y = Infinity;
      (a.segmentation || []).forEach(ring => {
        for (let i = 0; i + 1 < ring.length; i += 2) {
          if (ring[i + 1] < y || (ring[i + 1] === y && ring[i] < x)) {
            x = ring[i];
            y = ring[i + 1];
          }
        }
      });
      if (y === Infinity && a.bbox && a.bbox.length === 4) [x, y] = a.bbox;
      if (y === Infinity) {
        const k = this.keypoints(a)[0];
        if (k) [x, y] = k;
      }
      return y === Infinity ? null : [x, y];
    },
    nameLabels(img) {
      const v = this.viewOf(img);
      // image units per screen pixel ("meet" fits the whole view box)
      const unit = Math.max(v.w / this.picPx.w, v.h / this.picPx.h);
      const size = 12 * unit;
      const out = [];
      img.annotations.forEach(a => {
        const p = this.corner(a);
        if (!p) return;
        const c = this.categories[a.category_id];
        // just above the shape, or inside it at the top edge of the picture
        const y = p[1] - 3 * unit > v.y + size ? p[1] - 3 * unit : p[1] + size;
        out.push({ id: a.id, cat: a.category_id, x: p[0], y, size, text: c ? c.name : "?", color: (c && c.color) || "#00e5ff" });
      });
      return out;
    },
    colorOf(a) {
      const c = this.categories[a.category_id];
      return (c && c.color) || "#00e5ff";
    },
    async load() {
      this.loading = true;
      try {
        const r = await axios.get(`/api/review/dataset/${this.datasetId}/queue`, {
          params: { status: this.status, user: this.labeler, order: this.order, page: this.page, per_page: this.perPage }
        });
        const d = r.data;
        this.images = d.images || [];
        this.categories = Object.fromEntries((d.categories || []).map(c => [c.id, c]));
        this.labelers = d.labelers || [];
        this.canReview = !!d.can_review;
        this.datasetName = d.dataset_name || "";
        this.total = d.total;
        this.pages = d.pages;
        if (this.page > this.pages) {
          this.page = this.pages;
          if (this.total) return this.load();
        }
        this.decided = {};
        this.views = {};
        this.focus = 0;
        this.rejecting = null;
      } finally {
        this.loading = false;
        this.$nextTick(this.measure);
      }
    },
    go(page) {
      this.page = Math.max(1, page);
      this.load();
    },
    openImage(img) {
      this.$router.push({ name: "annotate", params: { identifier: img.id } });
    },
    startReject(img) {
      if (!this.canReview) return;
      this.rejecting = img.id;
      this.note = "";
      this.$nextTick(() => this.noteInput && this.noteInput.focus());
    },
    async act(img, action) {
      if (this.busy || !this.canReview) return;
      this.busy = true;
      try {
        await axios.post(`/api/review/image/${img.id}`, { action, note: action === "reject" ? this.note : "" });
        this.decided = { ...this.decided, [img.id]: action === "approve" ? "approved" : "rejected" };
        this.rejecting = null;
        this.afterDecision();
      } catch (e) {
        this.$toastr.error((e.response && e.response.data.message) || String(e));
      } finally {
        this.busy = false;
      }
    },
    async approveAll() {
      const ids = this.pending.map(i => i.id);
      if (!ids.length || this.busy) return;
      this.busy = true;
      try {
        await axios.post(`/api/review/image/${ids[0]}`, { action: "approve", image_ids: ids });
        const decided = { ...this.decided };
        ids.forEach(id => (decided[id] = "approved"));
        this.decided = decided;
        this.$toastr.success(this.$t("quickReview.approvedN", { n: ids.length }));
        this.afterDecision();
      } catch (e) {
        this.$toastr.error((e.response && e.response.data.message) || String(e));
      } finally {
        this.busy = false;
      }
    },
    /** next undecided image on the page, or the next page once all are done */
    afterDecision() {
      const next = this.images.findIndex((img, i) => i > this.focus && !this.decided[img.id]);
      const any = this.images.findIndex(img => !this.decided[img.id]);
      if (next >= 0) this.focus = next;
      else if (any >= 0) this.focus = any;
      else {
        // the page is done: the waiting ones move up (same page), other lists go on
        setTimeout(() => {
          if (this.status === "labeled" || this.status === "rejected") this.load();
          else if (this.page < this.pages) this.go(this.page + 1);
        }, 600);
      }
    },
    onKey(e) {
      if (modalOpen()) return;
      const tag = (e.target && e.target.tagName) || "";
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const img = this.images[this.focus];
      const cols = this.grid;
      const key = e.key.toLowerCase();
      const move = { arrowright: 1, arrowleft: -1, arrowdown: cols, arrowup: -cols }[key];
      if (move !== undefined) {
        e.preventDefault();
        const to = this.focus + move;
        if (to >= 0 && to < this.images.length) this.focus = to;
        else if (to >= this.images.length && this.page < this.pages) this.go(this.page + 1);
        else if (to < 0 && this.page > 1) this.go(this.page - 1);
        return;
      }
      if (key === "y" && e.shiftKey) {
        e.preventDefault();
        this.approveAll();
      } else if (key === "y" && img) {
        e.preventDefault();
        this.act(img, "approve");
      } else if (key === "x" && img) {
        e.preventDefault();
        this.startReject(img);
      } else if (key === "enter" && img) {
        e.preventDefault();
        this.openImage(img);
      } else if (key === "escape" && this.soloCat != null) {
        this.soloCat = null;
      } else if (key === "0" || key === "escape") {
        this.resetZoom();
      } else if (key === "h") {
        this.showShapes = !this.showShapes;
      } else if (key === "l") {
        this.showNames = !this.showNames;
      } else if (/^[1-4]$/.test(key)) {
        this.setGrid(parseInt(key, 10));
      } else if (key === "pagedown" || key === "n") {
        if (this.page < this.pages) this.go(this.page + 1);
      } else if (key === "pageup" || key === "p") {
        if (this.page > 1) this.go(this.page - 1);
      }
    }
  },
  created() {
    this.load();
    window.addEventListener("keydown", this.onKey);
    window.addEventListener("resize", this.measure);
  },
  beforeUnmount() {
    window.removeEventListener("keydown", this.onKey);
    window.removeEventListener("resize", this.measure);
  }
};
</script>

<style scoped>
.quick-review {
  background: #1f2430;
  height: 100vh;
  display: flex;
  flex-direction: column;
  text-align: left;
  color: #e9ecef;
}
.qr-bar {
  padding: 8px 16px;
  background: #2a2f3c;
  border-bottom: 1px solid #383e4c;
}
.qr-grid {
  flex: 1;
  min-height: 0;
  display: grid;
  gap: 8px;
  padding: 8px;
}
.tile {
  position: relative;
  display: flex;
  flex-direction: column;
  min-height: 0;
  min-width: 0;
  background: #14171f;
  border: 2px solid transparent;
  border-radius: 8px;
  overflow: hidden;
  cursor: pointer;
}
.tile.focus {
  border-color: #ffc107;
}
.tile.done .pic {
  opacity: 0.55;
}
.pic {
  flex: 1;
  min-height: 0;
  width: 100%;
}
.pic.zoomed {
  cursor: grab;
}
.pic.zoomed:active {
  cursor: grabbing;
}
.tile-foot {
  padding: 4px 8px;
  background: #262b37;
  font-size: 0.8rem;
}
.fname {
  font-weight: 600;
}
.meta {
  color: #adb5bd;
  font-size: 0.72rem;
}
.meta span + span::before {
  content: "·";
  margin: 0 5px;
}
.note {
  max-width: 220px;
}
.stamp {
  position: absolute;
  top: 10px;
  right: 10px;
  padding: 4px 10px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 0.85rem;
  color: #fff;
}
.stamp.approved {
  background: #198754;
}
.stamp.rejected {
  background: #dc3545;
}
.min-w-0 {
  min-width: 0;
}
.names text {
  font-weight: 700;
  stroke: rgba(0, 0, 0, 0.85);
  paint-order: stroke;
  stroke-linejoin: round;
}
.dim {
  opacity: 0.15;
}
.lit polygon {
  fill-opacity: 0.5;
}
.legend {
  position: absolute;
  top: 6px;
  left: 6px;
  max-width: calc(100% - 110px);
  max-height: 45%;
  overflow: auto;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  cursor: default;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(20, 23, 31, 0.82);
  font-size: 0.75rem;
  line-height: 1.4;
  white-space: nowrap;
}
.chip b {
  color: #adb5bd;
  font-weight: 600;
}
.chip {
  cursor: pointer;
}
.chip.on {
  box-shadow: inset 0 0 0 1.5px #ffc107;
}
.solo-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 3px 6px 3px 10px;
  border-radius: 999px;
  background: rgba(255, 193, 7, 0.15);
  border: 1px solid #ffc107;
  font-size: 0.8rem;
}
.solo-tag .btn-close {
  font-size: 0.6rem;
}
.chip.off {
  opacity: 0.35;
}
.dot {
  width: 9px;
  height: 9px;
  border-radius: 2px;
  display: inline-block;
}
.qr-empty {
  margin-top: 18vh;
}
.qr-help {
  padding: 2px 16px 6px;
}
</style>
