// Minimal replacement for vue-socket.io (Vue 2 only).
// Components keep declaring handlers in a `sockets: { event(data) {} }`
// option; `connect` / `disconnect` map to socket.io's lifecycle events.
import { io } from "socket.io-client";

export default {
  install(app, { connection = window.location.origin, options = {} } = {}) {
    const socket = io(connection, { transports: ["websocket", "polling"], ...options });
    app.config.globalProperties.$socket = socket;

    app.mixin({
      created() {
        const handlers = this.$options.sockets;
        if (!handlers) return;
        this.__socketHandlers = Object.entries(handlers).map(([event, fn]) => {
          const bound = fn.bind(this);
          socket.on(event, bound);
          // the component may be created after the socket already connected
          if (event === "connect" && socket.connected) bound();
          return [event, bound];
        });
      },
      beforeUnmount() {
        (this.__socketHandlers || []).forEach(([event, fn]) => socket.off(event, fn));
      }
    });
  }
};
