import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";
import store from "./store";
import paper from "paper";
import toastr from "toastr";
import FloatingVue from "floating-vue";
import { LoadingPlugin } from "vue-loading-overlay";
import VLazyImage from "v-lazy-image";
import socket from "./plugins/socket";

import "bootstrap";
import "bootstrap/dist/css/bootstrap.min.css";
import "./assets/bootstrap-compat.css";
import "font-awesome/css/font-awesome.min.css";
import "toastr/build/toastr.min.css";
import "floating-vue/dist/style.css";
import "vue-loading-overlay/dist/css/index.css";

// paper.js objects must never be wrapped in Vue reactive proxies: paper
// compares items by identity internally and deep-observing them is slow.
Object.defineProperty(paper.Base.prototype, "__v_skip", { value: true });

window.toastr = toastr;

const app = createApp(App);

app.config.globalProperties.$toastr = toastr;

app.use(router);
app.use(store);
app.use(FloatingVue, { themes: { tooltip: { delay: { show: 300, hide: 0 } } } });
app.use(LoadingPlugin);
app.use(socket, { connection: window.location.origin });
app.component("v-lazy-image", VLazyImage);

// vue-router 4 resolves the first route asynchronously
router.isReady().then(() => app.mount("#app"));
