import { reactive } from "vue";
import axios from "axios";

/**
 * The signed-in reviewer's saved reasons for rejecting, shared by the
 * annotator and quick review. ``list`` is null until loaded, or when the
 * user never saved any (then the built-in suggestions are shown).
 */
export const rejectReasons = reactive({ list: null, loaded: false });

let loading = null;

export function loadRejectReasons() {
  if (rejectReasons.loaded) return Promise.resolve();
  if (!loading) {
    loading = axios
      .get("/api/user/reject-reasons")
      .then(r => {
        rejectReasons.list = r.data.reasons;
        rejectReasons.loaded = true;
      })
      .catch(() => {})
      .finally(() => (loading = null));
  }
  return loading;
}

export async function saveRejectReasons(list) {
  const r = await axios.put("/api/user/reject-reasons", { reasons: list });
  rejectReasons.list = r.data.reasons;
  rejectReasons.loaded = true;
  return rejectReasons.list;
}

/** the reasons to show: the saved ones, or the suggestions */
export function reasonsOr(defaults) {
  return rejectReasons.list === null ? defaults : rejectReasons.list;
}

/** add a picked reason to what is typed already */
export function withReason(note, reason) {
  const text = (note || "").trim();
  if (!text) return reason;
  if (text.split(/[；;\n]/).map(s => s.trim()).includes(reason)) return text;
  return `${text}；${reason}`;
}
