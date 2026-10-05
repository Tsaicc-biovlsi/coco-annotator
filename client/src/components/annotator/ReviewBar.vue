<template>
  <div class="review-bar">
    <div class="d-flex align-items-center gap-2 flex-wrap">
      <span class="badge" :class="statusClass(status)">{{ $t('review.status.' + status) }}</span>
      <span v-if="review.assignee" class="small review-sub" :title="$t('review.assignee')">
        <i class="fa fa-user-o" /> {{ review.assignee }}
      </span>
    </div>

    <div v-if="status === 'rejected' && review.review_note" class="review-note mt-1">
      <i class="fa fa-commenting-o" /> {{ review.review_note }}
      <span v-if="review.reviewed_by" class="review-sub">— {{ review.reviewed_by }}</span>
    </div>
    <div v-else-if="status === 'labeled' && review.labeled_by" class="small review-sub mt-1">
      {{ $t('review.submittedBy', { name: review.labeled_by }) }}
    </div>
    <div v-else-if="status === 'approved' && review.reviewed_by" class="small review-sub mt-1">
      {{ $t('review.approvedBy', { name: review.reviewed_by }) }}
    </div>

    <div class="d-flex flex-wrap gap-1 mt-2">
      <button
        v-if="canEdit && (status === 'unlabeled' || status === 'rejected')"
        type="button"
        class="btn btn-sm btn-primary"
        :disabled="busy"
        @click="act('submit')"
      >
        <i class="fa fa-paper-plane" /> {{ $t('review.submit') }}
      </button>
      <template v-if="canReview && status !== 'unlabeled'">
        <button
          v-if="status !== 'approved'"
          type="button"
          class="btn btn-sm btn-success"
          :disabled="busy"
          @click="act('approve', null, true)"
        >
          <i class="fa fa-check" /> {{ $t('review.approve') }}
        </button>
        <button
          v-if="status !== 'rejected'"
          type="button"
          class="btn btn-sm btn-outline-danger"
          :disabled="busy"
          @click="rejecting = !rejecting"
        >
          <i class="fa fa-undo" /> {{ $t('review.reject') }}
        </button>
      </template>
      <button
        v-if="(status === 'labeled' && canEdit) || (status === 'approved' && canReview)"
        type="button"
        class="btn btn-sm btn-outline-secondary"
        :disabled="busy"
        @click="act('reopen')"
      >
        {{ $t('review.reopen') }}
      </button>
    </div>

    <div v-if="rejecting" class="mt-2">
      <textarea
        v-model="note"
        class="form-control form-control-sm"
        rows="2"
        :placeholder="$t('review.notePlaceholder')"
      />
      <div class="d-flex gap-1 mt-1">
        <button type="button" class="btn btn-sm btn-danger" :disabled="busy" @click="act('reject', note, true)">
          {{ $t('review.rejectConfirm') }}
        </button>
        <button type="button" class="btn btn-sm btn-link text-light" @click="rejecting = false">
          {{ $t('review.cancel') }}
        </button>
      </div>
    </div>

    <div class="form-check form-switch mt-2 small">
      <input id="reviewAutoNext" v-model="autoNext" class="form-check-input" type="checkbox" />
      <label class="form-check-label" for="reviewAutoNext">
        {{ canReview ? $t('review.autoNextReview') : $t('review.autoNextWork') }}
      </label>
    </div>
  </div>
</template>

<script>
import axios from "axios";

const AUTO_NEXT_KEY = "review/autoNext";

export function statusClass(status) {
  return {
    unlabeled: "text-bg-secondary",
    labeled: "text-bg-warning",
    approved: "text-bg-success",
    rejected: "text-bg-danger"
  }[status] || "text-bg-secondary";
}

export default {
  name: "ReviewBar",
  props: {
    imageId: { type: Number, required: true },
    datasetId: { type: Number, default: null },
    filename: { type: String, default: "" },
    review: { type: Object, default: () => ({}) },
    canEdit: { type: Boolean, default: false },
    canReview: { type: Boolean, default: false }
  },
  emits: ["updated", "navigate", "before-submit"],
  data() {
    let autoNext = true;
    try {
      autoNext = localStorage.getItem(AUTO_NEXT_KEY) !== "false";
    } catch {
      // storage unavailable: keep the default
    }
    return { busy: false, rejecting: false, note: "", autoNext };
  },
  computed: {
    status() {
      return this.review.status || "unlabeled";
    }
  },
  watch: {
    autoNext(value) {
      try {
        localStorage.setItem(AUTO_NEXT_KEY, String(value));
      } catch {
        // ignore
      }
    },
    imageId() {
      this.rejecting = false;
      this.note = "";
    }
  },
  methods: {
    statusClass,
    async act(action, note = null, reviewing = false) {
      this.busy = true;
      try {
        // the latest edits are saved before submitting
        if (action === "submit") {
          await Promise.race([
            new Promise(resolve => this.$emit("before-submit", resolve)),
            new Promise(resolve => setTimeout(resolve, 15000))
          ]);
        }
        const r = await axios.post(`/api/review/image/${this.imageId}`, { action, note: note || "" });
        this.$emit("updated", r.data);
        this.rejecting = false;
        this.note = "";
        this.$toastr.success(this.$t("review.done." + action));
        if (this.autoNext && (action === "submit" || reviewing)) await this.goNext(reviewing ? "review" : "work");
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      } finally {
        this.busy = false;
      }
    },
    async goNext(mode) {
      if (!this.datasetId) return;
      const r = await axios.get(`/api/review/dataset/${this.datasetId}/next`, {
        params: { mode, after: this.filename }
      });
      if (r.data.id && r.data.id !== this.imageId) {
        this.$emit("navigate", r.data.id);
      } else {
        this.$toastr.info(this.$t(mode === "review" ? "review.nothingToReview" : "review.nothingToDo"));
      }
    }
  }
};
</script>

<style scoped>
.review-bar {
  padding: 6px 10px;
  color: #e9ecef;
  font-size: 13px;
}
.review-sub {
  color: #ced4da;
}
.review-note {
  background: rgba(220, 53, 69, 0.15);
  border-left: 3px solid #dc3545;
  padding: 4px 6px;
  border-radius: 3px;
  white-space: pre-wrap;
}
</style>
