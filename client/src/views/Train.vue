<template>
  <div>
    <div style="padding-top: 55px" />
    <div class="bg-light train-page" style="overflow: auto; height: calc(100vh - 55px)">
      <div class="page-container py-4">
        <div class="d-flex align-items-start flex-wrap gap-2 mb-3">
          <div class="me-auto">
            <h3 class="mb-1"><i class="fa fa-graduation-cap" /> {{ $t('train.title') }}</h3>
            <div class="text-muted small">{{ $t('train.subtitle') }}</div>
          </div>
          <span v-if="status" class="trainer-pill" :class="status.alive ? 'ok' : 'down'">
            <i class="fa" :class="status.alive ? 'fa-check-circle' : 'fa-exclamation-circle'" />
            {{ status.alive ? $t('train.alive', { device: status.device || '?' }) : $t('train.down') }}
          </span>
        </div>
        <div v-if="status && !status.alive" class="alert alert-warning small">{{ $t('train.downHint') }}</div>

        <!-- a new training -->
        <div class="card p-3 shadow-sm mb-3">
          <h6 class="border-bottom pb-2"><b>{{ $t('train.new') }}</b></h6>
          <div v-if="!exports.length && !loading" class="text-muted small">{{ $t('train.noExports') }}</div>
          <div v-else class="row g-3">
            <div class="col-lg-6">
              <label class="form-label fw-semibold mb-1" for="trainExport">{{ $t('train.export') }}</label>
              <select id="trainExport" v-model="form.export_id" class="form-select form-select-sm">
                <option v-for="e in exports" :key="e.id" :value="e.id">{{ exportLabel(e) }}</option>
              </select>
              <div v-if="chosenExport" class="small text-muted mt-1">
                {{ $t('train.task') }}：<b>{{ $t('yolo.' + chosenExport.task) }}</b>
                · {{ $t('train.classes', { names: chosenExport.categories.join('、') || '—' }) }}
                <template v-if="chosenExport.split_counts">
                  · {{ $t('train.splitCounts', chosenExport.split_counts) }}
                </template>
              </div>
              <div v-if="chosenExport && !chosenExport.split" class="small text-warning-emphasis mt-1">
                <i class="fa fa-exclamation-triangle" /> {{ $t('train.noSplit') }}
              </div>

              <div class="fw-semibold mt-3 mb-1">{{ $t('train.start') }}</div>
              <div class="btn-group btn-group-sm mb-2" role="group">
                <button type="button" class="btn" :class="!form.fromModel ? 'btn-primary' : 'btn-outline-primary'" @click="form.fromModel = false">
                  {{ $t('train.fromBase') }}
                </button>
                <button type="button" class="btn" :class="form.fromModel ? 'btn-primary' : 'btn-outline-primary'" :disabled="!models.length" @click="form.fromModel = true">
                  {{ $t('train.fromModel') }}
                </button>
              </div>
              <template v-if="!form.fromModel">
                <div class="d-flex flex-wrap gap-2 align-items-center">
                  <select v-model="form.family" class="form-select form-select-sm w-auto">
                    <option v-for="f in (status && status.families) || ['yolo26']" :key="f" :value="f">{{ f.toUpperCase() }}</option>
                  </select>
                  <div class="btn-group btn-group-sm" role="group">
                    <button
                      v-for="s in (status && status.sizes) || ['n']"
                      :key="s"
                      type="button"
                      class="btn"
                      :class="form.size === s ? 'btn-secondary' : 'btn-outline-secondary'"
                      :title="$t('train.size.' + s)"
                      @click="form.size = s"
                    >{{ s }}</button>
                  </div>
                </div>
                <div class="small text-muted mt-1">
                  <code>{{ baseName }}</code> · {{ $t('train.size.' + form.size) }}
                </div>
              </template>
              <template v-else>
                <select v-model="form.base_model" class="form-select form-select-sm">
                  <option v-for="m in models" :key="m.name" :value="m.name">{{ m.name }}<template v-if="m.task"> ({{ m.task }})</template></option>
                </select>
                <div class="small text-muted mt-1">{{ $t('train.fromModelHint') }}</div>
              </template>
            </div>

            <div class="col-lg-6">
              <div class="row g-2">
                <div class="col-6">
                  <label class="form-label small mb-0" for="trainEpochs">{{ $t('train.epochs') }}</label>
                  <input id="trainEpochs" v-model.number="form.epochs" type="number" min="1" max="1000" class="form-control form-control-sm" />
                </div>
                <div class="col-6">
                  <label class="form-label small mb-0" for="trainImgsz">{{ $t('train.imgsz') }}</label>
                  <select id="trainImgsz" v-model.number="form.imgsz" class="form-select form-select-sm">
                    <option v-for="v in [320, 416, 512, 640, 768, 960, 1024, 1280]" :key="v" :value="v">{{ v }}</option>
                  </select>
                </div>
                <div class="col-6">
                  <label class="form-label small mb-0" for="trainBatch">{{ $t('train.batch') }}</label>
                  <select id="trainBatch" v-model.number="form.batch" class="form-select form-select-sm">
                    <option :value="-1">{{ $t('train.batchAuto') }}</option>
                    <option v-for="v in [4, 8, 16, 32, 64]" :key="v" :value="v">{{ v }}</option>
                  </select>
                </div>
                <div class="col-6">
                  <label class="form-label small mb-0" for="trainPatience">{{ $t('train.patience') }}</label>
                  <input id="trainPatience" v-model.number="form.patience" type="number" min="0" max="1000" class="form-control form-control-sm" />
                </div>
                <div class="col-12">
                  <label class="form-label small mb-0" for="trainName">{{ $t('train.name') }}</label>
                  <input id="trainName" v-model="form.name" class="form-control form-control-sm" :placeholder="chosenExport ? chosenExport.datasets.join(' + ') : ''" />
                </div>
              </div>
              <div class="small text-muted mt-2">{{ $t('train.paramsHint') }}</div>
              <div class="d-flex align-items-center gap-2 mt-3">
                <button type="button" class="btn btn-primary" :disabled="!form.export_id || busy" @click="start">
                  <i class="fa" :class="busy ? 'fa-spinner fa-spin' : 'fa-play'" /> {{ $t('train.go') }}
                </button>
                <span v-if="status && (status.running || status.queued)" class="small text-muted">
                  {{ $t('train.queueNow', { running: status.running, queued: status.queued }) }}
                </span>
              </div>
            </div>
          </div>
        </div>

        <!-- runs -->
        <div class="card p-3 shadow-sm">
          <h6 class="border-bottom pb-2 d-flex align-items-center">
            <b class="me-auto">{{ $t('train.runs') }}</b>
            <button type="button" class="btn btn-sm btn-outline-secondary py-0" @click="loadRuns"><i class="fa fa-refresh" /></button>
          </h6>
          <div v-if="!runs.length" class="text-muted small">{{ $t('train.noRuns') }}</div>
          <div v-for="r in runs" :key="r.id" class="run" :class="{ open: openId === r.id }">
            <div class="run-head" role="button" @click="toggle(r)">
              <span class="badge" :class="statusClass(r.status)">{{ $t('train.status.' + r.status) }}</span>
              <span class="fw-semibold text-truncate run-name">#{{ r.id }} {{ r.name }}</span>
              <span class="small text-muted text-nowrap">{{ $t('yolo.' + r.task) }} · {{ modelLabel(r) }}</span>
              <span class="run-progress">
                <span class="progress" style="height: 8px">
                  <span class="progress-bar" :class="r.status === 'failed' ? 'bg-danger' : 'bg-success'" :style="{ width: pct(r) + '%' }" />
                </span>
                <span class="small text-muted text-nowrap">
                  <template v-if="r.status === 'queued'">{{ $t('train.queuePos', { n: r.queue_position }) }}</template>
                  <template v-else>{{ r.epoch }} / {{ r.epochs }}</template>
                </span>
              </span>
              <span class="small text-nowrap metric" :title="mainMetricKey(r.last) || ''">{{ mainMetric(r.last) }}</span>
              <span class="small text-muted text-nowrap d-none d-md-inline">{{ r.creator }}</span>
              <i class="fa" :class="openId === r.id ? 'fa-chevron-up' : 'fa-chevron-down'" />
            </div>

            <div v-if="openId === r.id && detail" class="run-body">
              <div class="d-flex flex-wrap gap-2 align-items-center mb-2 small">
                <span>{{ $t('train.fromExport', { id: r.export_id, names: r.dataset_names.join(' + ') }) }}</span>
                <span class="text-muted">· epochs {{ r.params.epochs }} · imgsz {{ r.params.imgsz }} · batch {{ r.params.batch === -1 ? $t('train.batchAuto') : r.params.batch }} · patience {{ r.params.patience }}</span>
                <span class="ms-auto d-flex gap-2">
                  <button
                    v-if="r.status === 'running' || r.status === 'queued'"
                    type="button"
                    class="btn btn-sm btn-outline-danger"
                    :disabled="r.stop_requested"
                    @click="stop(r)"
                  >
                    <i class="fa fa-stop" />
                    {{ r.status === 'queued' ? $t('train.cancel') : r.stop_requested ? $t('train.stopping') : $t('train.stop') }}
                  </button>
                  <button v-else type="button" class="btn btn-sm btn-outline-secondary" @click="remove(r)">
                    <i class="fa fa-trash" /> {{ $t('train.remove') }}
                  </button>
                </span>
              </div>

              <div v-if="detail.model_name" class="alert alert-success py-2 small mb-2">
                <i class="fa fa-check" /> {{ $t('train.saved') }} <code>{{ detail.model_name }}</code>
                <RouterLink class="ms-2" to="/models">{{ $t('train.toModels') }}</RouterLink>
              </div>
              <div v-if="detail.error" class="alert alert-danger py-2 small mb-2 text-break">{{ detail.error }}</div>

              <div v-if="detail.metrics && detail.metrics.length" class="row g-2">
                <div class="col-md-6">
                  <MetricChart :rows="detail.metrics" :keys="metricKeys(detail.metrics)" :title="$t('train.chartMetrics')" :fixed-max="1" />
                </div>
                <div class="col-md-6">
                  <MetricChart :rows="detail.metrics" :keys="lossKeys(detail.metrics)" :title="$t('train.chartLoss')" />
                </div>
              </div>
              <div class="fw-semibold small mt-2 mb-1">{{ $t('train.log') }}</div>
              <pre ref="log" class="train-log">{{ detail.log_tail || '…' }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import MetricChart from "@/components/MetricChart.vue";

const POLL_MS = 3000;

/** Training YOLO models on the server (the trainer service runs them one at a time). */
export default {
  name: "TrainPage",
  components: { MetricChart },
  data() {
    return {
      status: null,
      exports: [],
      models: [],
      runs: [],
      loading: true,
      busy: false,
      openId: null,
      detail: null,
      timer: null,
      form: {
        export_id: null,
        fromModel: false,
        family: "yolo26",
        size: "n",
        base_model: "",
        epochs: 100,
        imgsz: 640,
        batch: -1,
        patience: 50,
        name: ""
      }
    };
  },
  computed: {
    chosenExport() {
      return this.exports.find(e => e.id === this.form.export_id) || null;
    },
    baseName() {
      const suffix = { detect: "", segment: "-seg", obb: "-obb", pose: "-pose", classify: "-cls" }[(this.chosenExport || {}).task] || "";
      return `${this.form.family}${this.form.size}${suffix}.pt`;
    }
  },
  methods: {
    async load() {
      this.loading = true;
      try {
        const [st, ex, md] = await Promise.all([
          axios.get("/api/train/status"),
          axios.get("/api/train/exports"),
          axios.get("/api/model/yolo").catch(() => ({ data: { models: [] } }))
        ]);
        this.status = st.data;
        this.exports = ex.data.exports || [];
        this.models = (md.data.models || []).filter(m => m.name);
        const wanted = Number(this.$route.query.export);
        if (wanted && this.exports.some(e => e.id === wanted)) this.form.export_id = wanted;
        else if (!this.chosenExport && this.exports.length) this.form.export_id = this.exports[0].id;
        if (!this.form.base_model && this.models.length) this.form.base_model = this.models[0].name;
      } finally {
        this.loading = false;
      }
      await this.loadRuns();
    },
    async loadRuns() {
      const r = await axios.get("/api/train/");
      this.runs = r.data.runs || [];
      if (this.openId != null) await this.loadDetail();
    },
    async loadDetail() {
      if (this.openId == null) return;
      const r = await axios.get(`/api/train/${this.openId}`);
      const atBottom = this.logAtBottom();
      this.detail = r.data;
      if (atBottom) this.$nextTick(() => this.scrollLog());
    },
    logAtBottom() {
      const el = this.$refs.log && (Array.isArray(this.$refs.log) ? this.$refs.log[0] : this.$refs.log);
      return !el || el.scrollHeight - el.scrollTop - el.clientHeight < 30;
    },
    scrollLog() {
      const el = this.$refs.log && (Array.isArray(this.$refs.log) ? this.$refs.log[0] : this.$refs.log);
      if (el) el.scrollTop = el.scrollHeight;
    },
    async poll() {
      try {
        const st = await axios.get("/api/train/status");
        this.status = st.data;
        if (this.runs.some(r => r.status === "running" || r.status === "queued") || this.openId != null) {
          await this.loadRuns();
        }
      } catch {
        // try again next time
      }
    },
    async toggle(r) {
      if (this.openId === r.id) {
        this.openId = null;
        this.detail = null;
        return;
      }
      this.openId = r.id;
      this.detail = null;
      await this.loadDetail();
      await this.$nextTick();
      this.scrollLog();
    },
    async start() {
      this.busy = true;
      try {
        const f = this.form;
        const body = { export_id: f.export_id, epochs: f.epochs, imgsz: f.imgsz, batch: f.batch, patience: f.patience, name: f.name };
        if (f.fromModel) body.base_model = f.base_model;
        else Object.assign(body, { family: f.family, size: f.size });
        const r = await axios.post("/api/train/", body);
        this.$toastr.success(this.$t("train.queued", { id: r.data.id }));
        this.openId = r.data.id;
        await this.loadRuns();
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      } finally {
        this.busy = false;
      }
    },
    async stop(r) {
      if (r.status === "running" && !confirm(this.$t("train.stopConfirm"))) return;
      await axios.post(`/api/train/${r.id}/stop`);
      await this.loadRuns();
    },
    async remove(r) {
      if (!confirm(this.$t("train.removeConfirm", { id: r.id }))) return;
      try {
        await axios.delete(`/api/train/${r.id}`);
        if (this.openId === r.id) {
          this.openId = null;
          this.detail = null;
        }
        await this.loadRuns();
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      }
    },
    exportLabel(e) {
      const parts = [`#${e.id}`, e.datasets.join(" + "), this.$t("yolo." + e.task)];
      if (e.split) parts.push(`${e.split.train}/${e.split.val}/${e.split.test}`);
      if (e.augment) parts.push(this.$t("train.augmented"));
      parts.push(new Date(e.created_at).toLocaleString());
      return parts.join(" · ");
    },
    modelLabel(r) {
      const p = r.params || {};
      return p.base_model || (p.family && p.size ? `${p.family}${p.size}` : p.model);
    },
    pct(r) {
      if (r.status === "done") return 100;
      return r.epochs ? Math.min(100, Math.round((100 * r.epoch) / r.epochs)) : 0;
    },
    statusClass(s) {
      return { queued: "text-bg-secondary", running: "text-bg-primary", done: "text-bg-success", failed: "text-bg-danger", stopped: "text-bg-warning" }[s];
    },
    /** the headline number: mAP50-95 (boxes, masks or poses), else top-1 accuracy */
    mainMetricKey(row) {
      if (!row) return null;
      return Object.keys(row).find(k => /^metrics\/mAP50-95/.test(k)) || Object.keys(row).find(k => /accuracy_top1/.test(k)) || null;
    },
    mainMetric(row) {
      const key = this.mainMetricKey(row);
      if (!key) return "";
      const name = /accuracy/.test(key) ? "top-1" : "mAP50-95";
      return `${name} ${row[key].toFixed(3)}`;
    },
    metricKeys(rows) {
      const keys = Object.keys(rows[rows.length - 1] || {});
      return keys.filter(k => k.startsWith("metrics/"));
    },
    lossKeys(rows) {
      const keys = Object.keys(rows[rows.length - 1] || {});
      return keys.filter(k => /loss/.test(k));
    }
  },
  mounted() {
    this.load();
    this.timer = setInterval(() => {
      if (!document.hidden) this.poll();
    }, POLL_MS);
  },
  beforeUnmount() {
    clearInterval(this.timer);
  }
};
</script>

<style scoped>
.page-container {
  text-align: left;
  max-width: 1200px;
  margin: 0 auto;
  padding-left: 16px;
  padding-right: 16px;
}
.trainer-pill {
  border-radius: 999px;
  padding: 4px 12px;
  font-size: 0.85rem;
  font-weight: 600;
}
.trainer-pill.ok {
  background: #d1e7dd;
  color: #0f5132;
}
.trainer-pill.down {
  background: #fff3cd;
  color: #664d03;
}
.run {
  border-bottom: 1px solid #e9ecef;
}
.run:last-child {
  border-bottom: 0;
}
.run-head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 2px;
}
.run-head:hover {
  background: #f8f9fa;
}
.run-name {
  flex: 1 1 auto;
  min-width: 0;
}
.run-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 200px;
  flex: none;
}
.run-progress .progress {
  flex: 1;
  display: flex;
}
.metric {
  width: 120px;
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.run-body {
  padding: 4px 4px 12px;
}
.train-log {
  background: #1e1e1e;
  color: #d4d4d4;
  font-size: 0.75rem;
  border-radius: 6px;
  padding: 8px 10px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
  margin: 0;
}
</style>
