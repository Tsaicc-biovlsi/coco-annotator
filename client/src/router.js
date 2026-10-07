import { createRouter, createWebHashHistory } from "vue-router";

// import Home from "@/views/Home.vue";
import About from "@/views/About.vue";
import Annotator from "@/views/Annotator.vue";
import AdminPanel from "@/views/AdminPanel.vue";
import Datasets from "@/views/Datasets.vue";
import Categories from "@/views/Categories.vue";
import Activity from "@/views/Activity.vue";
import Models from "@/views/Models.vue";
import Dataset from "@/views/Dataset.vue";
import Auth from "@/views/Auth.vue";
import User from "@/views/User.vue";
import Tasks from "@/views/Tasks.vue";
import PageNotFound from "@/views/PageNotFound.vue";

export default createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: "/about",
      name: "about",
      component: About
    },
    {
      alias: "/",
      path: "/datasets",
      name: "datasets",
      component: Datasets
    },
    {
      path: "/categories",
      name: "categories",
      component: Categories
    },
    {
      path: "/activity",
      name: "activity",
      component: Activity
    },
    {
      path: "/models",
      name: "models",
      component: Models
    },
    {
      path: "/trash",
      redirect: { path: "/activity", query: { group: "trash" } }
    },
    {
      path: "/undo",
      redirect: { path: "/activity", query: { group: "trash" } }
    },
    {
      path: "/annotate/:identifier",
      name: "annotate",
      component: Annotator,
      props: true
    },
    {
      path: "/dataset/:identifier",
      name: "dataset",
      component: Dataset,
      props: true
    },
    {
      path: "/auth",
      name: "authentication",
      component: Auth,
      props: true
    },
    {
      path: "/user",
      name: "user",
      component: User
    },
    {
      path: "/admin/panel",
      name: "admin",
      component: AdminPanel
    },
    {
      path: "/tasks",
      name: "tasks",
      component: Tasks
    },
    { path: "/:pathMatch(.*)*", component: PageNotFound }
  ]
});
