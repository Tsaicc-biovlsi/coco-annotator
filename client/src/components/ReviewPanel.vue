<template>
  <div class="review-panel">
    <!-- overall progress -->
    <div class="card my-3 p-3 shadow-sm">
      <div class="d-flex align-items-center flex-wrap gap-2 border-bottom pb-2 mb-3">
        <h6 class="mb-0 me-auto"><b>{{ $t('review.progressTitle') }}</b></h6>
        <button
          v-if="progress && progress.can_review"
          type="button"
          class="btn btn-sm btn-warning"
          :disabled="!progress.total.labeled"
          @click="openNext('review')"
        >
          <i class="fa fa-search" /> {{ $t('review.startReview', { n: progress.total.labeled }) }}
        </button>
        <RouterLink
          v-if="progress && progress.can_review"
          :to="`/review/${datasetId}`"
          class="btn btn-sm btn-outline-warning"
          :title="$t('quickReview.hint')"
        >
          <i class="fa fa-th" /> {{ $t('quickReview.title') }}
        </RouterLink>
        <button type="button" class="btn btn-sm btn-primary" :disabled="!myOpen" @click="openNext('work')">
          <i class="fa fa-pencil" /> {{ $t('review.startWork', { n: myOpen }) }}
        </button>
        <button type="button" class="btn btn-sm btn-outline-secondary" @click="load">
          <i class="fa fa-refresh" />
        </button>
      </div>

      <div v-if="!progress" class="text-muted small"><i class="fa fa-spinner fa-spin" /></div>
      <template v-else>
        <div class="progress-stacked" style="height: 22px">
          <div
            v-for="s in STATUSES"
            :key="s"
            class="progress"
            role="progressbar"
            :style="{ width: pct(progress.total[s]) + '%' }"
            :title="$t('review.status.' + s) + ': ' + progress.total[s]"
          >
            <div class="progress-bar" :class="barClass(s)">
              <template v-if="pct(progress.total[s]) >= 8">{{ progress.total[s] }}</template>
            </div>
          </div>
        </div>
        <div class="d-flex flex-wrap gap-3 small mt-2">
          <span v-for="s in STATUSES" :key="s">
            <span class="badge" :class="statusClass(s)">{{ $t('review.status.' + s) }}</span>
            {{ progress.total[s] }}（{{ pct(progress.total[s]) }}%）
          </span>
          <span class="ms-auto text-muted">{{ $t('review.totalImages', { n: progress.images }) }}</span>
        </div>
      </template>
    </div>

    <!-- per member -->
    <div v-if="progress" class="card my-3 p-3 shadow-sm">
      <h6 class="border-bottom pb-2"><b>{{ $t('review.byMember') }}</b></h6>
      <div class="table-responsive">
        <table class="table table-sm align-middle mb-0 text-center">
          <thead>
            <tr>
              <th class="text-start">{{ $t('review.member') }}</th>
              <th>{{ $t('review.assigned') }}</th>
              <th v-for="s in STATUSES" :key="s">{{ $t('review.status.' + s) }}</th>
              <th style="width: 30%">{{ $t('review.approvedPct') }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in memberRows" :key="row.username || '-'">
              <td class="text-start">
                <template v-if="row.username">
                  {{ row.username }}
                  <span v-if="progress.reviewers.includes(row.username)" class="badge text-bg-info ms-1">
                    {{ $t('review.reviewer') }}
                  </span>
                  <span v-if="row.username === progress.owner" class="badge text-bg-dark ms-1">{{ $t('review.owner') }}</span>
                </template>
                <span v-else class="text-muted">{{ $t('review.unassigned') }}</span>
              </td>
              <td>{{ row.assigned }}</td>
              <td v-for="s in STATUSES" :key="s">{{ row[s] || 0 }}</td>
              <td>
                <div class="progress" style="height: 8px" :title="rowPct(row) + '%'">
                  <div class="progress-bar bg-success" :style="{ width: rowPct(row) + '%' }" />
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- assign -->
    <div v-if="progress && (progress.can_assign ?? progress.can_review)" class="card my-3 p-3 shadow-sm">
      <h6 class="border-bottom pb-2"><b>{{ $t('review.assignTitle') }}</b></h6>
      <div class="small text-muted mb-2">{{ $t('review.assignHint') }}</div>
      <div class="d-flex flex-wrap gap-3 mb-2">
        <div v-for="name in progress.members" :key="name" class="form-check">
          <input :id="'assign-' + name" v-model="assignTo" class="form-check-input" type="checkbox" :value="name" />
          <label class="form-check-label" :for="'assign-' + name">{{ name }}</label>
        </div>
      </div>
      <div class="d-flex flex-wrap align-items-center gap-2">
        <select v-model="scope" class="form-select form-select-sm" style="max-width: 280px">
          <option value="unassigned">{{ $t('review.scope.unassigned', { n: progress.unassigned ? sumRow(progress.unassigned) : 0 }) }}</option>
          <option value="unlabeled">{{ $t('review.scope.unlabeled', { n: progress.total.unlabeled + progress.total.rejected }) }}</option>
          <option value="all">{{ $t('review.scope.all', { n: progress.images }) }}</option>
        </select>
        <button type="button" class="btn btn-sm btn-primary" :disabled="!assignTo.length || busy" @click="assign">
          <i class="fa fa-random" /> {{ $t('review.assignEven', { n: assignTo.length }) }}
        </button>
        <button type="button" class="btn btn-sm btn-outline-danger ms-auto" :disabled="busy" @click="unassignAll">
          {{ $t('review.unassignAll') }}
        </button>
      </div>
    </div>

    <!-- reviewers -->
    <div v-if="progress && (progress.is_creator ?? progress.is_owner)" class="card my-3 p-3 shadow-sm">
      <h6 class="border-bottom pb-2"><b>{{ $t('review.reviewersTitle') }}</b></h6>
      <div class="small text-muted mb-2">{{ $t('review.reviewersHint') }}</div>
      <div class="d-flex flex-wrap gap-3 mb-2">
        <div v-for="name in progress.members.filter(n => n !== progress.owner)" :key="name" class="form-check">
          <input :id="'reviewer-' + name" v-model="reviewers" class="form-check-input" type="checkbox" :value="name" />
          <label class="form-check-label" :for="'reviewer-' + name">{{ name }}</label>
        </div>
        <span v-if="progress.members.length <= 1" class="small text-muted">{{ $t('review.noMembers') }}</span>
      </div>
      <div>
        <button type="button" class="btn btn-sm btn-outline-primary" :disabled="busy" @click="saveReviewers">
          {{ $t('review.saveReviewers') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { statusClass } from "@/components/annotator/ReviewBar.vue";

const STATUSES = ["unlabeled", "labeled", "approved", "rejected"];

export default {
  name: "ReviewPanel",
  props: {
    datasetId: { type: Number, required: true }
  },
  emits: ["changed"],
  data() {
    return { STATUSES, progress: null, assignTo: [], scope: "unassigned", reviewers: [], busy: false };
  },
  computed: {
    memberRows() {
      if (!this.progress) return [];
      const byName = Object.fromEntries(this.progress.people.map(p => [p.username, p]));
      const rows = this.progress.members.map(name => {
        const counts = byName[name] || {};
        return { username: name, ...counts, assigned: this.sumRow(counts) };
      });
      // assignees who are no longer members
      this.progress.people.filter(p => !this.progress.members.includes(p.username))
        .forEach(p => rows.push({ ...p, assigned: this.sumRow(p) }));
      rows.push({ username: "", ...this.progress.unassigned, assigned: this.sumRow(this.progress.unassigned) });
      return rows;
    },
    /** my images that still need work */
    myOpen() {
      if (!this.progress) return 0;
      const mine = this.progress.people.find(p => p.username === this.progress.me) || {};
      return (mine.unlabeled || 0) + (mine.rejected || 0);
    }
  },
  watch: {
    datasetId: {
      immediate: true,
      handler(id) {
        if (id) this.load();
      }
    }
  },
  methods: {
    statusClass,
    barClass(s) {
      return { unlabeled: "bg-secondary", labeled: "bg-warning", approved: "bg-success", rejected: "bg-danger" }[s];
    },
    sumRow(row) {
      return STATUSES.reduce((n, s) => n + ((row && row[s]) || 0), 0);
    },
    pct(n) {
      return this.progress && this.progress.images ? Math.round((100 * n) / this.progress.images) : 0;
    },
    rowPct(row) {
      const total = this.sumRow(row);
      return total ? Math.round((100 * (row.approved || 0)) / total) : 0;
    },
    load() {
      return axios.get(`/api/review/dataset/${this.datasetId}/progress`).then(r => {
        this.progress = r.data;
        this.reviewers = [...r.data.reviewers];
        if (!this.assignTo.length) {
          // default: everybody except the owner
          this.assignTo = r.data.members.filter(n => n !== r.data.owner);
        }
      });
    },
    async assign() {
      if (!confirm(this.$t("review.assignConfirm", { n: this.assignTo.length }))) return;
      await this.post("assign", { usernames: this.assignTo, scope: this.scope }, r => {
        const parts = Object.entries(r.data.assigned).map(([k, v]) => `${k} ${v}`);
        this.$toastr.success(this.$t("review.assigned_done", { list: parts.join("、") }));
      });
    },
    async unassignAll() {
      if (!confirm(this.$t("review.unassignConfirm"))) return;
      await this.post("assign", { usernames: [], scope: "all" }, () => this.$toastr.success(this.$t("review.unassigned_done")));
    },
    async saveReviewers() {
      await this.post("reviewers", { reviewers: this.reviewers }, () => this.$toastr.success(this.$t("review.reviewersSaved")));
    },
    async post(path, body, onDone) {
      this.busy = true;
      try {
        const r = await axios.post(`/api/review/dataset/${this.datasetId}/${path}`, body);
        onDone(r);
        await this.load();
        this.$emit("changed");
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      } finally {
        this.busy = false;
      }
    },
    async openNext(mode) {
      const r = await axios.get(`/api/review/dataset/${this.datasetId}/next`, { params: { mode } });
      if (r.data.id) {
        this.$router.push({ name: "annotate", params: { identifier: r.data.id } });
      } else {
        this.$toastr.info(this.$t(mode === "review" ? "review.nothingToReview" : "review.nothingToDo"));
      }
    }
  }
};
</script>
