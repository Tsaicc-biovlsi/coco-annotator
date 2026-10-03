<template>
  <div style="margin: 10px">
    <div class="card">

      <div class="card-header text-start" @click="showTasks = !showTasks">
        {{ $tr('taskGroup', name) }}

        <span style="float: right; color: light-gray">
          {{ $t('task.running', { running: runningTasks.length, total: tasks.length }, tasks.length) }}
        </span>
      </div>

      <div v-show="showTasks" class="card-body">
        <Task :key="index" v-for="(task, index) in tasks" :task="task" />
      </div>
    </div>
  </div>
</template>

<script>
import Task from "@/components/tasks/Task.vue";

export default {
  name: "TaskGroup",
  components: { Task },
  props: {
    tasks: {
      type: Array,
      required: true
    },
    name: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      showTasks: true
    };
  },
  computed: {
    runningTasks() {
      return this.tasks.filter(t => t.progress < 100);
    }
  }
};
</script>

<style scoped>
.card {
  margin: 0;
  padding: 0;
  cursor: pointer;
}

.card-header {
  color: white;
  background-color: #383c4a;
}

.card-body {
  padding: 0;
  margin: 0;
}
</style>
