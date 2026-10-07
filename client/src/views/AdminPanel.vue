<template>
  <div>
    <div style="padding-top: 55px" />
    <div
      class="album py-5 bg-light"
      style="overflow: auto; height: calc(100vh - 55px)"
    >
      <div class="container">
        <h2 class="text-center">{{ $t('adminPanel.title') }}</h2>
        <ul class="nav nav-tabs mb-3 justify-content-center">
          <li class="nav-item">
            <a class="nav-link" :class="{ active: tab === 'users' }" href="#" @click.prevent="tab = 'users'">
              <i class="fa fa-users" /> {{ $t('adminPanel.users') }}
            </a>
          </li>
          <li class="nav-item">
            <a class="nav-link" :class="{ active: tab === 'roles' }" href="#" @click.prevent="tab = 'roles'">
              <i class="fa fa-id-badge" /> {{ $t('roles.title') }}
            </a>
          </li>
        </ul>

        <p v-show="tab === 'users'" class="text-center">
          <i18n-t keypath="admin.total" tag="span"><template #n><strong>{{ total }}</strong></template></i18n-t>
        </p>

        <div v-show="tab === 'users'" class="row justify-content-md-center">
          <div
            class="col-md-auto btn-group"
            role="group"
            style="padding-bottom: 20px"
          >
            <button
              type="button"
              class="btn btn-success"
              data-bs-toggle="modal"
              data-bs-target="#createUser"
            >
              {{ $t('adminPanel.createUser') }}
            </button>
            <button type="button" class="btn btn-primary" @click="$refs.bulk.open()">
              {{ $t('bulkUsers.title') }}
            </button>
            <button type="button" class="btn btn-secondary" @click="updatePage">
              {{ $t('adminPanel.refresh') }}
            </button>
          </div>
        </div>

        <div v-show="tab === 'users'" class="row justify-content-md-center" style="padding-bottom: 10px">
          <div class="col-md-2 text-end">
            <span>{{ $t('adminPanel.limit') }}</span>
          </div>
          <div class="col-md-2">
            <select
              v-model="limit"
              class="form-select form-select-sm text-inline"
            >
              <option>50</option>
              <option>100</option>
              <option>500</option>
              <option>1000</option>
            </select>
          </div>
        </div>

        <div v-show="tab === 'users'">
          <table class="table table-hover table-sm align-middle">
            <thead class="remove-top-border">
              <tr>
                <th scope="col">{{ $t('adminPanel.username') }}</th>
                <th scope="col">{{ $t('adminPanel.name') }}</th>
                <th scope="col">{{ $t('roles.role') }}</th>
                <th class="text-center" scope="col">{{ $t('adminPanel.edit') }}</th>
                <th class="text-center" scope="col">
                  {{ $t('adminPanel.delete') }}
                </th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="(user, index) in users" :key="index">
                <td>
                  {{ user.username }}
                  <small v-if="isSelf(user)" class="text-muted">{{ $t('adminPanel.you') }}</small>
                </td>
                <td>{{ user.name }}</td>
                <td class="role-cell">
                  <select
                    v-if="canChangeRole(user)"
                    class="form-select form-select-sm"
                    :value="user.role"
                    @change="setRole(user, $event.target.value)"
                  >
                    <option v-for="r in assignableRoles" :key="r.key" :value="r.key">{{ roleName(r) }}</option>
                  </select>
                  <span v-else class="badge" :class="user.role === 'admin' ? 'bg-danger' : 'bg-secondary'">
                    {{ roleName(user.role) }}
                  </span>
                </td>
                <td class="text-center">
                  <i
                    v-if="mayTouch(user)"
                    class="fa fa-pencil edit-icon"
                    :title="$t('adminPanel.edit')"
                    @click="editUser(user)"
                  />
                </td>
                <td class="text-center">
                  <i
                    v-if="!isSelf(user) && mayTouch(user)"
                    class="fa fa-remove delete-icon"
                    :title="$t('adminPanel.delete')"
                    @click="deleteUser(user)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-show="tab === 'roles'" class="roles text-start">
          <p class="text-muted small text-center">{{ $t('roles.help') }}</p>
          <div class="table-responsive">
            <table class="table table-sm align-middle roles-table">
              <thead>
                <tr>
                  <th rowspan="2">{{ $t('roles.role') }}</th>
                  <th :colspan="pagePerms.length" class="text-center group-head">{{ $t('roles.groupPages') }}</th>
                  <th :colspan="managePerms.length" class="text-center group-head">{{ $t('roles.groupManage') }}</th>
                  <th rowspan="2" class="text-center">{{ $t('roles.users') }}</th>
                  <th v-if="isAdmin" rowspan="2"></th>
                </tr>
                <tr>
                  <th v-for="p in permissions" :key="p" class="text-center perm-head" :title="$t('roles.permHelp.' + p)">
                    {{ $t('roles.perm.' + p) }} <i class="fa fa-question-circle text-muted" />
                  </th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="r in roles" :key="r.key">
                  <td>
                    <input
                      v-if="isAdmin && !r.builtin"
                      v-model="r.name"
                      class="form-control form-control-sm role-name"
                      @change="saveRole(r, { name: r.name })"
                      @keyup.enter="$event.target.blur()"
                    />
                    <span v-else>
                      <strong>{{ roleName(r) }}</strong>
                      <small class="text-muted d-block">{{ $t('roles.builtin.' + r.key + 'Hint') }}</small>
                    </span>
                  </td>
                  <td v-for="p in permissions" :key="p" class="text-center">
                    <input
                      type="checkbox"
                      class="form-check-input"
                      :checked="r.permissions.includes(p)"
                      :disabled="!isAdmin || r.key === 'admin'"
                      @change="togglePerm(r, p, $event.target.checked)"
                    />
                  </td>
                  <td class="text-center">{{ r.users }}</td>
                  <td v-if="isAdmin" class="text-center">
                    <i
                      v-if="!r.builtin"
                      class="fa fa-trash delete-icon"
                      :title="$t('roles.delete')"
                      @click="deleteRole(r)"
                    />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <form v-if="isAdmin" class="d-flex gap-2 justify-content-center" @submit.prevent="addRole">
            <input
              v-model="newRole"
              class="form-control form-control-sm new-role"
              :placeholder="$t('roles.newPlaceholder')"
            />
            <button type="submit" class="btn btn-success btn-sm" :disabled="!newRole.trim()">
              <i class="fa fa-plus" /> {{ $t('roles.add') }}
            </button>
          </form>
          <p v-else class="text-muted small text-center">{{ $t('roles.adminsOnly') }}</p>
        </div>
      </div>
    </div>

    <div class="modal fade" tabindex="-1" role="dialog" id="createUser">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('adminPanel.createAUser') }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <form>
              <div
                class="mb-3"
                :class="{ 'was-validated': create.username.length !== 0 }"
              >
                <label>{{ $t('adminPanel.username') }}</label>
                <input
                  v-model="create.username"
                  class="form-control"
                  :placeholder="$t('adminPanel.username')"
                  required
                />
              </div>
              <div
                class="mb-3"
                :class="{ 'was-validated': create.password.length !== 0 }"
              >
                <label>{{ $t('adminPanel.password') }}</label>
                <input
                  v-model="create.password"
                  class="form-control"
                  :placeholder="$t('adminPanel.password')"
                  required
                />
              </div>
              <div
                class="mb-3"
                :class="{ 'was-validated': create.name.length !== 0 }"
              >
                <label>{{ $t('adminPanel.name') }}</label>
                <input
                  v-model="create.name"
                  class="form-control"
                  :placeholder="$t('adminPanel.name')"
                  required
                />
              </div>
              <div>
                <label>{{ $t('roles.role') }}</label>
                <select v-model="create.role" class="form-select">
                  <option v-for="r in assignableRoles" :key="r.key" :value="r.key">{{ roleName(r) }}</option>
                </select>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="submit" class="btn btn-primary" @click="createUser">
              {{ $t('adminPanel.createUser') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('adminPanel.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <div class="modal fade" tabindex="-1" role="dialog" id="editUser">
      <div class="modal-dialog" role="document">
        <div class="modal-content">
          <div class="modal-header">
            <h5 class="modal-title">{{ $t('adminPanel.editUser', { username: edit.username }) }}</h5>
            <button
              type="button"
              class="btn-close"
              data-bs-dismiss="modal"
              aria-label="Close"
            ></button>
          </div>
          <div class="modal-body">
            <form @submit.prevent="saveUser">
              <div class="mb-3">
                <label>{{ $t('adminPanel.name') }}</label>
                <input
                  v-model="edit.name"
                  class="form-control"
                  :placeholder="$t('adminPanel.name')"
                />
              </div>
              <div class="mb-3">
                <label>{{ $t('adminPanel.newPassword') }}</label>
                <input
                  v-model="edit.password"
                  type="password"
                  autocomplete="new-password"
                  class="form-control"
                  :placeholder="$t('adminPanel.leaveBlankToKeep')"
                />
              </div>
              <div>
                <label>{{ $t('roles.role') }}</label>
                <select v-model="edit.role" class="form-select" :disabled="edit.self">
                  <option v-for="r in assignableRoles" :key="r.key" :value="r.key">{{ roleName(r) }}</option>
                </select>
                <small v-if="edit.self" class="d-block text-muted mt-1">
                  {{ $t('roles.cannotChangeOwn') }}
                </small>
              </div>
            </form>
          </div>
          <div class="modal-footer">
            <button type="button" class="btn btn-primary" @click="saveUser">
              {{ $t('adminPanel.save') }}
            </button>
            <button
              type="button"
              class="btn btn-secondary"
              data-bs-dismiss="modal"
            >
              {{ $t('adminPanel.close') }}
            </button>
          </div>
        </div>
      </div>
    </div>
    <BulkUsersModal ref="bulk" @created="updatePage" />
  </div>
</template>

<script>
import axios from "axios";
import AdminPanel from "@/models/admin";
import toastrs from "@/mixins/toastrs";
import { mapMutations } from "vuex";
import { showModal, hideModal } from "@/libs/modal";
import BulkUsersModal from "@/components/BulkUsersModal.vue";

const PAGES = ["activity", "models", "tasks"];

export default {
  name: "AdminPanel",
  components: { BulkUsersModal },
  mixins: [toastrs],
  data() {
    return {
      tab: "users",
      users: [],
      roles: [],
      permissions: [],
      newRole: "",
      limit: 50,
      total: 0,
      create: {
        name: "",
        username: "",
        role: "user",
        password: ""
      },
      edit: {
        username: "",
        name: "",
        password: "",
        role: "user",
        self: false
      }
    };
  },
  computed: {
    isAdmin() {
      return this.$store.getters["user/isAdmin"];
    },
    pagePerms() {
      return this.permissions.filter(p => PAGES.includes(p));
    },
    managePerms() {
      return this.permissions.filter(p => !PAGES.includes(p));
    },
    /** Only admins hand out the admin role */
    assignableRoles() {
      return this.roles.filter(r => this.isAdmin || r.key !== "admin");
    }
  },
  methods: {
    ...mapMutations(["addProcess", "removeProcess"]),
    error(title, error) {
      const data = (error && error.response && error.response.data) || {};
      this.axiosReqestError(title, data.message || String(error));
    },
    updatePage() {
      let process = "Loading users";
      this.addProcess(process);

      AdminPanel.getUsers(this.limit)
        .then(response => {
          this.users = response.data.users;
          this.total = response.data.total;
        })
        .finally(() => this.removeProcess(process));
      this.loadRoles();
    },
    loadRoles() {
      return axios.get("/api/admin/roles").then(r => this.applyRoles(r.data));
    },
    applyRoles(data) {
      this.roles = data.roles || [];
      this.permissions = data.permissions || [];
    },
    roleName(role) {
      const r = typeof role === "string" ? this.roles.find(x => x.key === role) || { key: role } : role;
      if (r.key === "admin" || r.key === "user") return this.$t("roles.builtin." + r.key);
      return r.name || r.key;
    },
    mayTouch(user) {
      return this.isAdmin || user.role !== "admin";
    },
    canChangeRole(user) {
      return !this.isSelf(user) && this.mayTouch(user);
    },
    setRole(user, role) {
      const before = user.role;
      user.role = role;
      AdminPanel.editUser(user.username, { name: "", password: "", role })
        .then(response => {
          user.role = response.data.role;
          user.is_admin = response.data.is_admin;
          this.loadRoles();
        })
        .catch(error => {
          user.role = before;
          this.error("Edit User", error);
        });
    },
    createUser(event) {
      event.preventDefault();

      AdminPanel.createUser(this.create)
        .then(() => {
          hideModal("#createUser");
          this.create = { name: "", username: "", role: "user", password: "" };
          this.updatePage();
        })
        .catch(error => this.error("Create User", error));
    },
    isSelf(user) {
      const me = this.$store.state.user.user;
      return !!me && me.username.toLowerCase() === user.username.toLowerCase();
    },
    editUser(user) {
      this.edit = {
        username: user.username,
        name: user.name || "",
        password: "",
        role: user.role || "user",
        self: this.isSelf(user)
      };
      showModal("#editUser");
    },
    saveUser() {
      const changes = { name: this.edit.name, password: this.edit.password };
      if (!this.edit.self) changes.role = this.edit.role;

      AdminPanel.editUser(this.edit.username, changes)
        .then(() => {
          hideModal("#editUser");
          this.updatePage();
        })
        .catch(error => this.error("Edit User", error));
    },
    deleteUser(user) {
      let yes = confirm(
        "Are you sure you want to delete " +
          user.username +
          ". This action cannot be undone."
      );
      if (!yes) return;

      AdminPanel.deleteUser(user.username)
        .then(this.updatePage)
        .catch(error => this.error("Delete User", error));
    },
    addRole() {
      const name = this.newRole.trim();
      if (!name) return;
      axios
        .post("/api/admin/roles", { name, permissions: [] })
        .then(r => {
          this.applyRoles(r.data);
          this.newRole = "";
        })
        .catch(error => this.error(this.$t("roles.add"), error));
    },
    saveRole(role, changes) {
      return axios
        .put(`/api/admin/roles/${role.key}`, changes)
        .then(r => this.applyRoles(r.data))
        .catch(error => {
          this.error(this.$t("roles.title"), error);
          this.loadRoles();
        });
    },
    togglePerm(role, perm, on) {
      const perms = on ? [...role.permissions, perm] : role.permissions.filter(p => p !== perm);
      role.permissions = perms;
      this.saveRole(role, { permissions: perms });
    },
    deleteRole(role) {
      if (!confirm(this.$t("roles.confirmDelete", { name: this.roleName(role), n: role.users }))) return;
      axios
        .delete(`/api/admin/roles/${role.key}`)
        .then(r => {
          this.applyRoles(r.data);
          this.updatePage();
        })
        .catch(error => this.error(this.$t("roles.delete"), error));
    }
  },
  watch: {
    limit: "updatePage"
  },
  created() {
    this.updatePage();
  }
};
</script>

<style scoped>
.remove-top-border {
  border: none !important;
}

.fa {
  margin: 0;
  padding: 2px;
}

.edit-icon:hover {
  color: green;
}

.delete-icon:hover {
  color: red;
}

.role-cell select {
  max-width: 180px;
}

.roles {
  max-width: 1100px;
  margin: 0 auto;
}

.roles-table .group-head {
  border-bottom: 2px solid #dee2e6;
  font-size: 0.85rem;
  color: #6c757d;
}

.perm-head {
  font-size: 0.85rem;
  white-space: nowrap;
  cursor: help;
}

.role-name {
  min-width: 140px;
}

.new-role {
  max-width: 240px;
}
</style>
