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
    <button
      v-if="status === 'rejected' && regions.length"
      type="button"
      class="btn btn-sm btn-outline-warning mt-1 py-0"
      @click="$emit('show-regions')"
    >
      <i class="fa fa-crosshairs" /> {{ $t('review.showRegions', { n: regions.length }) }}
    </button>
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
        <i class="fa" :class="canReview ? 'fa-check' : 'fa-paper-plane'" />
        {{ canReview ? $t('review.submitApprove') : $t('review.submit') }}
      </button>
      <template v-if="canReview && status !== 'unlabeled'">
        <button
          v-if="status !== 'approved'"
          type="button"
          class="btn btn-sm btn-success"
          :disabled="busy"
          @click="act('approve')"
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
        ref="note"
        v-model="note"
        class="form-control form-control-sm"
        rows="2"
        :placeholder="$t('review.notePlaceholder')"
        @keydown.enter.ctrl.prevent="act('reject', note)"
        @keydown.esc.prevent="rejecting = false"
        @keydown.exact="onNoteKey"
      />
      <RejectReasons ref="reasons" class="mt-1" :note="note" @pick="pickReason" />
      <div v-if="getRegion" class="form-check small mt-1" :title="$t('review.attachViewHint')">
        <input id="reviewAttachView" v-model="attachView" class="form-check-input" type="checkbox" />
        <label class="form-check-label" for="reviewAttachView">{{ $t('review.attachView') }}</label>
      </div>
      <div class="d-flex gap-1 mt-1">
        <button type="button" class="btn btn-sm btn-danger" :disabled="busy" @click="act('reject', note)">
          {{ $t('review.rejectConfirm') }}
        </button>
        <button type="button" class="btn btn-sm btn-link text-light" @click="rejecting = false">
          {{ $t('review.cancel') }}
        </button>
      </div>
    </div>

    <div v-if="canEdit" class="form-check form-switch mt-2 small">
      <input id="reviewSubmitOnNext" v-model="submitOnNext" class="form-check-input" type="checkbox" />
      <label class="form-check-label" for="reviewSubmitOnNext" :title="$t('review.submitOnNextHint')">
        {{ $t('review.submitOnNext') }}
      </label>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import RejectReasons from "@/components/RejectReasons.vue";
import { withReason } from "@/libs/rejectReasons";

const SUBMIT_ON_NEXT_KEY = "review/submitOnNext";
// an empty image is submitted on N only after it was open this long
const EMPTY_MIN_MS = 2000;

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
  components: { RejectReasons },
  props: {
    imageId: { type: Number, required: true },
    datasetId: { type: Number, default: null },
    filename: { type: String, default: "" },
    review: { type: Object, default: () => ({}) },
    canEdit: { type: Boolean, default: false },
    canReview: { type: Boolean, default: false },
    // the zoomed-in part of the image, {x, y, w, h} (null when not zoomed)
    getRegion: { type: Function, default: null }
  },
  emits: ["updated", "before-submit", "show-regions"],
  data() {
    let submitOnNext = false;
    try {
      submitOnNext = localStorage.getItem(SUBMIT_ON_NEXT_KEY) === "true";
    } catch {
      // storage unavailable: off
    }
    return { busy: false, rejecting: false, note: "", submitOnNext, attachView: true };
  },
  computed: {
    regions() {
      return this.review.review_regions || [];
    },
    status() {
      return this.review.status || "unlabeled";
    }
  },
  created() {
    // when this image was opened (an empty image left at once is not submitted)
    this.openedAt = Date.now();
  },
  watch: {
    submitOnNext(value) {
      try {
        localStorage.setItem(SUBMIT_ON_NEXT_KEY, String(value));
      } catch {
        // ignore
      }
    },
    imageId() {
      this.rejecting = false;
      this.note = "";
      this.openedAt = Date.now();
    }
  },
  methods: {
    statusClass,
    async act(action, note = null) {
      if (this.busy) return;
      this.busy = true;
      try {
        // the latest edits are saved before submitting; not saved, not submitted
        if (action === "submit") {
          const saved = await Promise.race([
            new Promise(resolve => this.$emit("before-submit", resolve)),
            new Promise(resolve => setTimeout(() => resolve(false), 15000))
          ]);
          if (saved === false) {
            this.$toastr.warning(this.$t("review.notSaved"));
            return;
          }
        }
        const body = { action, note: note || "" };
        if (action === "reject" && this.attachView && this.getRegion) {
          const v = this.getRegion();
          if (v) body.regions = [[v.x, v.y, v.w, v.h]];
        }
        const r = await axios.post(`/api/review/image/${this.imageId}`, body);
        this.$emit("updated", r.data);
        this.rejecting = false;
        this.note = "";
        const approvedOwn = action === "submit" && r.data.status === "approved";
        this.$toastr.success(this.$t(approvedOwn ? "review.done.selfApprove" : "review.done." + action));
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
      } finally {
        this.busy = false;
      }
    },
    /** a number key in the empty reason box picks that saved reason */
    onNoteKey(e) {
      const r = this.$refs.reasons && this.$refs.reasons.forKey(e, this.note);
      if (!r) return;
      e.preventDefault();
      this.pickReason(r);
    },
    pickReason(r) {
      this.note = withReason(this.note, r);
      this.$nextTick(() => this.$refs.note && this.$refs.note.focus());
    },
    /** Y: approve (reviewers) or "done" (annotators), whichever this image offers */
    shortcutApprove() {
      if (this.busy) return;
      if (this.canEdit && (this.status === "unlabeled" || this.status === "rejected")) this.act("submit");
      else if (this.canReview && this.status !== "unlabeled" && this.status !== "approved") this.act("approve");
      else this.$toastr.info(this.$t("review.nothingToApprove"));
    },
    /** X: open the reject box (Ctrl+Enter sends, Esc closes) */
    shortcutReject() {
      if (this.busy || !this.canReview || this.status === "unlabeled" || this.status === "rejected") {
        this.$toastr.info(this.$t("review.nothingToReject"));
        return;
      }
      this.rejecting = true;
      this.$nextTick(() => this.$refs.note && this.$refs.note.focus());
    },
    /**
     * Called when moving to the next image (N or the arrow), after saving:
     * with the switch on, an image not submitted yet is submitted, also
     * one with nothing to annotate. An empty image passed by within 2
     * seconds (holding N to skip ahead) is not. Never stops the move.
     */
    async submitBeforeNext() {
      if (!this.submitOnNext || !this.canEdit || !(this.status === "unlabeled" || this.status === "rejected")) return;
      const glanced = Date.now() - (this.openedAt || 0) < EMPTY_MIN_MS;
      try {
        const r = await axios.post(`/api/review/image/${this.imageId}`, { action: "submit", skip_empty: glanced });
        if (!r.data.skipped) {
          this.$emit("updated", r.data);
          this.$toastr.success(this.$t(r.data.status === "approved" ? "review.approvedOnNext" : "review.submittedOnNext",
            { name: this.filename }));
        }
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || String(error));
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
