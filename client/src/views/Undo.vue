<template>
  <div>
    <div style="padding-top: 55px" />
    <div
      class="album py-5 bg-light"
      style="overflow: auto; height: calc(100vh - 55px)"
    >
      <div class="container">
        <h2 class="text-center">{{ $t('undo.undo') }}</h2>
        <p class="text-center">
          <i18n-t keypath="undo.total" tag="span"><template #n><strong>{{ undos.length }}</strong></template></i18n-t>
        </p>

        <div class="row justify-content-md-center">
          <div
            class="col-md-auto btn-group"
            role="group"
            style="padding-bottom: 20px"
          >
            <button type="button" class="btn btn-success disabled">
              {{ $t('undo.undoAll') }}
            </button>
            <button type="button" class="btn btn-danger disabled">
              {{ $t('undo.deleteAll') }}
            </button>
            <button type="button" class="btn btn-secondary" @click="updatePage">
              {{ $t('undo.refresh') }}
            </button>
          </div>
        </div>

        <div class="row justify-content-md-center" style="padding-bottom: 10px">
          <div class="col-md-2 text-end">
            <span>{{ $t('undo.instanceType') }}</span>
          </div>
          <div class="col-md-2">
            <select v-model="type" class="form-select form-select-sm">
              <option value="all">{{ $t('undo.all') }}</option>
              <option value="annotation">{{ $t('undo.annotations') }}</option>
              <option value="category">{{ $t('undo.categories') }}</option>
              <option value="dataset">{{ $t('undo.datasets') }}</option>
            </select>
          </div>
          <div class="col-md-2 text-end">
            <span>{{ $t('undo.limit') }}</span>
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

        <p class="text-center" v-if="undos.length < 1">{{ $t('undo.nothingToUndone') }}</p>
        <div v-else>
          <table class="table table-hover table-sm">
            <thead class="remove-top-border">
              <tr>
                <th scope="col">{{ $t('undo.date') }}</th>
                <th scope="col">{{ $t('undo.instanceType') }}</th>
                <th scope="col">{{ $t('undo.id') }}</th>
                <th scope="col">{{ $t('undo.name') }}</th>
                <th class="text-center" scope="col">{{ $t('undo.rollback') }}</th>
                <th class="text-center" scope="col">{{ $t('undo.delete') }}</th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="(undo, index) in undos" :key="index">
                <td>
                  {{ $t('common.ago', { time: $ago(undo.ago) }) }}
                </td>
                <td>{{ undo.instance }}</td>
                <td>{{ undo.id }}</td>
                <td>{{ undo.name }}</td>
                <td>
                  <i
                    class="fa fa-undo text-center undo-icon"
                    aria-hidden="true"
                    @click="undoModel(undo.id, undo.instance)"
                  />
                </td>
                <td>
                  <i
                    class="fa fa-remove text-center delete-icon"
                    aria-hidden="true"
                    @click="deleteModel(undo.id, undo.instance)"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import Undo from "@/models/undos";

import { mapMutations } from "vuex";

export default {
  name: "Undo",
  data() {
    return {
      undos: [],
      limit: 50,
      type: "all"
    };
  },
  methods: {
    ...mapMutations(["addProcess", "removeProcess"]),
    updatePage() {
      let process = "Loading undo for " + this.type + " instance type";
      this.addProcess(process);

      Undo.all(this.limit, this.type)
        .then(response => {
          this.undos = response.data;
        })
        .finally(() => this.removeProcess(process));
    },
    undoModel(id, instance) {
      Undo.undo(id, instance).then(this.updatePage);
    },
    deleteModel(id, instance) {
      Undo.delete(id, instance).then(this.updatePage);
    }
  },
  watch: {
    limit: "updatePage",
    type: "updatePage"
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

.undo-icon:hover {
  color: green;
}

.delete-icon:hover {
  color: red;
}
</style>
