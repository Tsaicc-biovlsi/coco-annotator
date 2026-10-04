<template>
  <div class="modal fade" tabindex="-1" role="dialog" id="bulkUsers">
    <div class="modal-dialog modal-lg" role="document">
      <div class="modal-content text-start">
        <div class="modal-header">
          <h5 class="modal-title">{{ $t('bulkUsers.title') }}</h5>
          <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
        </div>

        <div class="modal-body">
          <template v-if="!result">
            <label class="form-label" for="bulkUsersText">{{ $t('bulkUsers.list') }}</label>
            <textarea
              id="bulkUsersText"
              v-model="text"
              class="form-control font-monospace"
              rows="10"
              :placeholder="'B11223344,王小明\nB11223345,陳小華\nB11223346,林大同,自訂密碼'"
            ></textarea>
            <div class="form-text">{{ $t('bulkUsers.listHint') }}</div>

            <div class="d-flex align-items-center gap-2 mt-2">
              <button type="button" class="btn btn-outline-secondary btn-sm" @click="$refs.csv.click()">
                <i class="fa fa-file-text-o" /> {{ $t('bulkUsers.loadCsv') }}
              </button>
              <input ref="csv" type="file" accept=".csv,.txt,text/csv,text/plain" class="d-none" @change="loadCsv" />
              <span class="text-muted small">
                {{ $t('bulkUsers.preview', { valid: parsed.valid.length, invalid: parsed.invalid.length }) }}
              </span>
            </div>
            <div v-if="parsed.invalid.length" class="small text-danger mt-1">
              {{ $t('bulkUsers.invalidRows', { rows: parsed.invalid.slice(0, 5).join('、') }) }}
            </div>

            <div class="mt-3">
              <label class="form-label" for="bulkUsersDataset">{{ $t('bulkUsers.dataset') }}</label>
              <select id="bulkUsersDataset" v-model="datasetId" class="form-select">
                <option :value="null">{{ $t('bulkUsers.noDataset') }}</option>
                <option v-for="d in datasets" :key="d.id" :value="d.id">{{ d.name }}</option>
              </select>
            </div>
          </template>

          <template v-else>
            <div class="alert alert-success py-2">
              {{ $t('bulkUsers.done', { created: result.created.length, existing: result.existing.length }) }}
            </div>
            <div v-if="result.created.length" class="alert alert-warning py-2 small">
              {{ $t('bulkUsers.saveNow') }}
            </div>
            <div class="table-responsive" style="max-height: 320px">
              <table class="table table-sm">
                <thead>
                  <tr>
                    <th>{{ $t('adminPanel.username') }}</th>
                    <th>{{ $t('adminPanel.name') }}</th>
                    <th>{{ $t('adminPanel.password') }}</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="u in result.created" :key="u.username">
                    <td>{{ u.username }}</td>
                    <td>{{ u.name }}</td>
                    <td class="font-monospace">{{ u.password }}</td>
                  </tr>
                  <tr v-for="name in result.existing" :key="'e' + name" class="text-muted">
                    <td>{{ name }}</td>
                    <td colspan="2">{{ $t('bulkUsers.alreadyExists') }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
        </div>

        <div class="modal-footer">
          <template v-if="!result">
            <button type="button" class="btn btn-primary" :disabled="!parsed.valid.length || running" @click="submit">
              <i v-if="running" class="fa fa-spinner fa-spin" />
              {{ $t('bulkUsers.create', { n: parsed.valid.length }) }}
            </button>
          </template>
          <template v-else>
            <button v-if="result.created.length" type="button" class="btn btn-success" @click="download">
              <i class="fa fa-download" /> {{ $t('bulkUsers.download') }}
            </button>
          </template>
          <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">{{ $t('adminPanel.close') }}</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import axios from "axios";
import { showModal } from "@/libs/modal";

const STUDENT_ID = /^[A-Za-z][0-9]{8}$/;

export default {
  name: "BulkUsersModal",
  emits: ["created"],
  data() {
    return { text: "", datasetId: null, datasets: [], result: null, running: false };
  },
  computed: {
    /** One user per line: student id, name, optional password (comma, tab or space separated) */
    parsed() {
      const valid = [];
      const invalid = [];
      const seen = new Set();
      this.text.split(/\r?\n/).forEach((line, i) => {
        const raw = line.trim();
        if (!raw) return;
        const parts = raw.split(/\s*[,\t;，]\s*|\s+/).filter(Boolean);
        const username = (parts[0] || "").toUpperCase();
        // a header line such as "學號,姓名" is ignored
        if (i === 0 && !STUDENT_ID.test(username) && /學號|帳號|id|user/i.test(raw)) return;
        if (!STUDENT_ID.test(username)) {
          invalid.push(parts[0] || raw);
          return;
        }
        if (seen.has(username)) {
          invalid.push(`${username} (${this.$t("bulkUsers.duplicate")})`);
          return;
        }
        seen.add(username);
        valid.push({ username, name: parts[1] || "", password: parts[2] || "" });
      });
      return { valid, invalid };
    }
  },
  methods: {
    open() {
      this.text = "";
      this.result = null;
      this.datasetId = null;
      showModal("#bulkUsers");
      axios.get("/api/dataset/").then(r => {
        this.datasets = (r.data || []).sort((a, b) => a.name.localeCompare(b.name));
      });
    },
    loadCsv(event) {
      const file = event.target.files[0];
      event.target.value = "";
      if (!file) return;
      const reader = new FileReader();
      reader.onload = () => {
        // drop a UTF-8 BOM (Excel)
        this.text = String(reader.result).replace(/^\uFEFF/, "");
      };
      reader.readAsText(file, "utf-8");
    },
    submit() {
      this.running = true;
      axios
        .post("/api/admin/users/bulk", { users: this.parsed.valid, datasetId: this.datasetId })
        .then(r => {
          this.result = r.data;
          this.$emit("created");
        })
        .catch(error => {
          const data = (error.response && error.response.data) || {};
          this.$toastr.error(data.message || String(error), this.$t("bulkUsers.title"));
        })
        .finally(() => (this.running = false));
    },
    download() {
      const rows = [["username", "name", "password"], ...this.result.created.map(u => [u.username, u.name, u.password])];
      const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g, '""')}"`).join(",")).join("\r\n");
      // BOM so Excel opens Chinese names correctly
      const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
      const link = document.createElement("a");
      link.href = URL.createObjectURL(blob);
      link.download = `accounts-${new Date().toISOString().slice(0, 10)}.csv`;
      link.click();
      URL.revokeObjectURL(link.href);
    }
  }
};
</script>
