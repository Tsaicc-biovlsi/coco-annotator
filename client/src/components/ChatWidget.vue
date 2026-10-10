<template>
  <div class="chat-widget" :class="'side-' + side">
    <!-- a short preview of a new message while the chat is closed -->
    <transition name="chat-fade">
      <button v-if="!open && preview" type="button" class="chat-preview shadow" @click="toggle(true)">
        <b>{{ preview.name }}</b>：{{ preview.text || (preview.file_name ? '🖼 ' + preview.file_name : '') }}
      </button>
    </transition>

    <button
      v-show="!open"
      type="button"
      class="chat-fab shadow"
      :title="$t('chat.open')"
      :aria-label="$t('chat.open')"
      @click="toggle(true)"
    >
      <i class="fa fa-comments" />
      <span v-if="unread" class="chat-badge">{{ unread > 99 ? '99+' : unread }}</span>
    </button>

    <section v-if="open" class="chat-panel shadow-lg" role="dialog" :aria-label="$t('chat.title')" @keydown.stop>
      <header class="chat-head">
        <i class="fa fa-comments me-2" />
        <span class="text-truncate flex-grow-1">
          <b>{{ $t('chat.title') }}</b>
          <span v-if="datasetName" class="chat-room ms-1">· {{ datasetName }}</span>
        </span>
        <button type="button" class="btn-close btn-close-white" :aria-label="$t('chat.close')" @click="toggle(false)" />
      </header>

      <div ref="list" class="chat-list" @scroll="onScroll">
        <div v-if="more" class="text-center my-1">
          <button type="button" class="btn btn-link btn-sm p-0" :disabled="loadingOlder" @click="loadOlder">
            <i v-if="loadingOlder" class="fa fa-spinner fa-spin" /> {{ $t('chat.older') }}
          </button>
        </div>
        <div v-if="loaded && !messages.length" class="chat-empty">{{ $t('chat.empty') }}</div>

        <template v-for="(m, i) in messages" :key="m.id">
          <div v-if="dayChanged(i)" class="chat-day">{{ dayLabel(m.created_at) }}</div>
          <div v-if="m.id === firstUnreadId" class="chat-new-line"><span>{{ $t('chat.newMessages') }}</span></div>
          <div class="chat-msg" :class="{ mine: m.user === me, cont: grouped(i) }">
            <div v-if="!grouped(i)" class="chat-meta">
              <span class="chat-name">{{ m.user === me ? $t('chat.you') : m.name }}</span>
              <span class="chat-time">{{ timeLabel(m.created_at) }}</span>
            </div>
            <div class="chat-bubble" :title="fullTime(m.created_at)">
              <span v-if="m.text" class="chat-text">{{ m.text }}</span>
              <a
                v-if="m.image_id"
                href="#"
                class="chat-image"
                :class="{ current: m.image_id === imageId }"
                :title="m.image_id === imageId ? $t('chat.thisImage') : $t('chat.openImage')"
                @click.prevent="openImage(m)"
              >
                <i class="fa fa-picture-o" /> {{ m.file_name || ('#' + m.image_id) }}
              </a>
            </div>
          </div>
        </template>
      </div>

      <button v-if="!atBottom && newBelow" type="button" class="chat-jump" @click="scrollToBottom(true)">
        <i class="fa fa-arrow-down" /> {{ $t('chat.newBelow', { n: newBelow }) }}
      </button>

      <footer class="chat-input">
        <div v-if="attach && imageId" class="chat-attach">
          <i class="fa fa-picture-o" /> <span class="text-truncate">{{ imageName || ('#' + imageId) }}</span>
          <button type="button" class="btn-close btn-sm ms-auto" :aria-label="$t('chat.detach')" @click="attach = false" />
        </div>
        <div class="d-flex align-items-end gap-1">
          <button
            v-if="imageId"
            type="button"
            class="btn btn-sm chat-attach-btn"
            :class="attach ? 'btn-primary' : 'btn-outline-secondary'"
            :title="$t('chat.attach')"
            :aria-label="$t('chat.attach')"
            :aria-pressed="attach"
            @click="attach = !attach"
          >
            <i class="fa fa-picture-o" />
          </button>
          <textarea
            ref="input"
            v-model="text"
            class="form-control form-control-sm"
            rows="1"
            :maxlength="MAX"
            :placeholder="$t('chat.placeholder')"
            :title="$t('chat.keysHint')"
            @keydown.enter="onEnter"
            @input="autosize"
          />
          <button
            type="button"
            class="btn btn-sm btn-primary"
            :disabled="sending || (!text.trim() && !(attach && imageId))"
            :aria-label="$t('chat.send')"
            :title="$t('chat.send')"
            @click="send"
          >
            <i class="fa" :class="sending ? 'fa-spinner fa-spin' : 'fa-paper-plane'" />
          </button>
        </div>
      </footer>
    </section>
  </div>
</template>

<script>
import axios from "axios";

const MAX = 1000;

function readOpen() {
  try {
    return localStorage.getItem("chat/open") === "1";
  } catch {
    return false;
  }
}

/** The dataset's chat room: a button in the corner and a small panel. */
export default {
  name: "ChatWidget",
  props: {
    datasetId: { type: Number, default: null },
    datasetName: { type: String, default: "" },
    // on the annotator: the image open there (can be attached to a message)
    imageId: { type: Number, default: null },
    imageName: { type: String, default: "" },
    side: { type: String, default: "right" }
  },
  data() {
    return {
      MAX,
      open: readOpen(),
      messages: [],
      me: null,
      more: false,
      loaded: false,
      loadingOlder: false,
      unread: 0,
      lastRead: 0,
      firstUnreadId: null,
      text: "",
      attach: false,
      sending: false,
      atBottom: true,
      newBelow: 0,
      preview: null,
      previewTimer: null,
      readTimer: null
    };
  },
  watch: {
    datasetId: {
      immediate: true,
      handler(id, old) {
        if (old != null) this.$socket.emit("watch_chat", { dataset_id: null, leave: old });
        this.messages = [];
        this.loaded = false;
        this.unread = 0;
        if (id != null) {
          this.watch();
          this.load();
        }
      }
    },
    imageId() {
      this.attach = false;
    }
  },
  beforeUnmount() {
    clearTimeout(this.previewTimer);
    clearTimeout(this.readTimer);
    if (this.datasetId != null) this.$socket.emit("watch_chat", { dataset_id: null, leave: this.datasetId });
  },
  methods: {
    watch() {
      this.$socket.emit("watch_chat", { dataset_id: this.datasetId });
    },
    async load() {
      const id = this.datasetId;
      try {
        const r = await axios.get(`/api/chat/dataset/${id}`);
        if (id !== this.datasetId) return;
        this.messages = r.data.messages;
        this.more = r.data.more;
        this.me = r.data.me;
        this.lastRead = r.data.last_read;
        this.unread = r.data.unread;
        this.markFirstUnread();
        this.loaded = true;
        if (this.open) {
          this.scrollToBottom(true);
          this.markRead();
        }
      } catch {
        // the chat is extra: the page works without it
      }
    },
    markFirstUnread() {
      const m = this.messages.find(m => m.id > this.lastRead && m.user !== this.me);
      this.firstUnreadId = m ? m.id : null;
    },
    async loadOlder() {
      if (!this.messages.length || this.loadingOlder) return;
      this.loadingOlder = true;
      const list = this.$refs.list;
      const before = list ? list.scrollHeight - list.scrollTop : 0;
      try {
        const r = await axios.get(`/api/chat/dataset/${this.datasetId}`, { params: { before: this.messages[0].id } });
        this.messages = [...r.data.messages, ...this.messages];
        this.more = r.data.more;
        this.$nextTick(() => {
          // keep the messages that were on screen where they were
          if (list) list.scrollTop = list.scrollHeight - before;
        });
      } finally {
        this.loadingOlder = false;
      }
    },
    toggle(open) {
      this.open = open;
      try {
        localStorage.setItem("chat/open", open ? "1" : "0");
      } catch {
        // not remembered
      }
      if (open) {
        this.preview = null;
        this.markFirstUnread();
        this.$nextTick(() => {
          this.scrollToBottom(true);
          if (this.$refs.input) this.$refs.input.focus();
        });
        this.markRead();
      }
    },
    markRead() {
      const last = this.messages[this.messages.length - 1];
      if (!last || last.id <= this.lastRead) {
        this.unread = 0;
        return;
      }
      this.lastRead = last.id;
      this.unread = 0;
      clearTimeout(this.readTimer);
      this.readTimer = setTimeout(() => {
        axios.post(`/api/chat/dataset/${this.datasetId}/read`, { last_id: last.id }).catch(() => {});
      }, 300);
    },
    onEnter(e) {
      // Enter sends, Shift+Enter is a new line; not while picking characters (IME)
      if (e.shiftKey || e.isComposing || e.keyCode === 229) return;
      e.preventDefault();
      this.send();
    },
    autosize() {
      const el = this.$refs.input;
      if (!el) return;
      el.style.height = "auto";
      el.style.height = Math.min(el.scrollHeight, 110) + "px";
    },
    async send() {
      const text = this.text.trim();
      const imageId = this.attach && this.imageId ? this.imageId : null;
      if ((!text && !imageId) || this.sending) return;
      this.sending = true;
      try {
        const r = await axios.post(`/api/chat/dataset/${this.datasetId}`, { text, image_id: imageId });
        this.add(r.data);
        this.text = "";
        this.attach = false;
        this.$nextTick(() => {
          this.autosize();
          this.scrollToBottom(true);
        });
      } catch (error) {
        const data = (error.response && error.response.data) || {};
        this.$toastr.error(data.message || this.$t("chat.failed"));
      } finally {
        this.sending = false;
      }
    },
    /** a message (ours from the reply, anyone's from the socket), once */
    add(m) {
      if (this.messages.some(x => x.id === m.id)) return false;
      this.messages.push(m);
      return true;
    },
    onScroll() {
      const el = this.$refs.list;
      if (!el) return;
      this.atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
      if (this.atBottom) this.newBelow = 0;
    },
    scrollToBottom(force) {
      const el = this.$refs.list;
      if (!el || (!force && !this.atBottom)) return;
      el.scrollTop = el.scrollHeight;
      this.atBottom = true;
      this.newBelow = 0;
    },
    openImage(m) {
      if (m.image_id === this.imageId) return;
      this.$router.push({ name: "annotate", params: { identifier: m.image_id } });
    },
    when(iso) {
      return iso ? new Date(iso) : null;
    },
    timeLabel(iso) {
      const d = this.when(iso);
      return d ? d.toLocaleTimeString(this.$i18n.locale, { hour: "2-digit", minute: "2-digit", hour12: false }) : "";
    },
    fullTime(iso) {
      const d = this.when(iso);
      return d ? d.toLocaleString(this.$i18n.locale, { hour12: false }) : "";
    },
    dayLabel(iso) {
      const d = this.when(iso);
      if (!d) return "";
      const today = new Date();
      const yesterday = new Date(today.getTime() - 86400000);
      if (d.toDateString() === today.toDateString()) return this.$t("chat.today");
      if (d.toDateString() === yesterday.toDateString()) return this.$t("chat.yesterday");
      return d.toLocaleDateString(this.$i18n.locale);
    },
    dayChanged(i) {
      if (i === 0) return true;
      const a = this.when(this.messages[i - 1].created_at);
      const b = this.when(this.messages[i].created_at);
      return !a || !b || a.toDateString() !== b.toDateString();
    },
    /** the same person again within 5 minutes: no name / time line */
    grouped(i) {
      if (i === 0 || this.dayChanged(i)) return false;
      const prev = this.messages[i - 1];
      const m = this.messages[i];
      if (prev.user !== m.user || m.id === this.firstUnreadId) return false;
      return this.when(m.created_at) - this.when(prev.created_at) < 5 * 60 * 1000;
    }
  },
  sockets: {
    connect() {
      // a new connection starts without rooms; catch up on what was missed
      if (this.datasetId != null) {
        this.watch();
        if (this.loaded) this.load();
      }
    },
    chat(m) {
      if (!m || m.dataset_id !== this.datasetId) return;
      if (!this.add(m)) return;
      if (m.user === this.me) return;
      if (this.open && !document.hidden) {
        if (this.atBottom) this.$nextTick(() => this.scrollToBottom(true));
        else this.newBelow += 1;
        this.markRead();
      } else {
        this.unread += 1;
        if (!this.open) {
          this.preview = m;
          clearTimeout(this.previewTimer);
          this.previewTimer = setTimeout(() => (this.preview = null), 5000);
        }
      }
    }
  },
  mounted() {
    this.onVisible = () => {
      if (!document.hidden && this.open && this.unread) this.markRead();
    };
    document.addEventListener("visibilitychange", this.onVisible);
  },
  unmounted() {
    document.removeEventListener("visibilitychange", this.onVisible);
  }
};
</script>

<style scoped>
.chat-widget {
  position: fixed;
  bottom: 18px;
  z-index: 1040;
}
.chat-widget.side-right {
  right: 18px;
}
/* the annotator: right of its tool bar */
.chat-widget.side-left {
  left: 54px;
}
.chat-fab {
  position: relative;
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: 0;
  background: #2563eb;
  color: #fff;
  font-size: 1.35rem;
  transition: transform 0.15s, background 0.15s;
}
.chat-fab:hover {
  background: #1d4ed8;
  transform: translateY(-2px);
}
.chat-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 11px;
  background: #dc3545;
  color: #fff;
  font-size: 0.75rem;
  font-weight: 700;
  line-height: 22px;
  border: 2px solid #fff;
}
.chat-preview {
  position: absolute;
  bottom: 60px;
  max-width: 260px;
  width: max-content;
  padding: 8px 12px;
  border: 0;
  border-radius: 12px;
  background: #fff;
  color: #212529;
  font-size: 0.85rem;
  text-align: left;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.side-right .chat-preview {
  right: 0;
}
.side-left .chat-preview {
  left: 0;
}
.chat-panel {
  position: relative;
  width: 340px;
  max-width: calc(100vw - 36px);
  height: 480px;
  max-height: calc(100vh - 36px);
  display: flex;
  flex-direction: column;
  background: #fff;
  color: #212529;
  border-radius: 12px;
  overflow: hidden;
  text-align: left;
}
.chat-head {
  display: flex;
  align-items: center;
  padding: 10px 12px;
  background: #2563eb;
  color: #fff;
  font-size: 0.95rem;
}
.chat-room {
  font-weight: 400;
  opacity: 0.85;
}
.chat-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px 10px;
  background: #f5f7fb;
  scrollbar-width: thin;
}
.chat-empty {
  margin-top: 40%;
  text-align: center;
  color: #6c757d;
  font-size: 0.85rem;
}
.chat-day {
  margin: 10px 0 6px;
  text-align: center;
  font-size: 0.72rem;
  color: #6c757d;
}
.chat-new-line {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 8px 0 4px;
  color: #dc3545;
  font-size: 0.72rem;
}
.chat-new-line::before,
.chat-new-line::after {
  content: "";
  flex: 1;
  border-top: 1px solid rgba(220, 53, 69, 0.5);
}
.chat-msg {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  margin-top: 8px;
}
.chat-msg.cont {
  margin-top: 2px;
}
.chat-msg.mine {
  align-items: flex-end;
}
.chat-meta {
  font-size: 0.72rem;
  color: #6c757d;
  margin: 0 4px 2px;
}
.chat-name {
  font-weight: 600;
  color: #495057;
  margin-right: 6px;
}
.chat-bubble {
  max-width: 85%;
  padding: 6px 10px;
  border-radius: 12px;
  background: #fff;
  border: 1px solid #e3e7ee;
  font-size: 0.875rem;
  line-height: 1.4;
}
.chat-msg.mine .chat-bubble {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}
.chat-text {
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}
.chat-image {
  display: block;
  margin-top: 2px;
  font-size: 0.8rem;
  overflow-wrap: anywhere;
}
.chat-text + .chat-image {
  margin-top: 4px;
}
.chat-msg.mine .chat-image {
  color: #dbe7ff;
}
.chat-image.current {
  cursor: default;
  text-decoration: none;
  opacity: 0.8;
}
.chat-jump {
  position: absolute;
  bottom: 70px;
  left: 50%;
  transform: translateX(-50%);
  border: 0;
  border-radius: 999px;
  padding: 3px 12px;
  background: #212529;
  color: #fff;
  font-size: 0.75rem;
  opacity: 0.85;
}
.chat-input {
  padding: 8px;
  border-top: 1px solid #e3e7ee;
  background: #fff;
}
.chat-input textarea {
  resize: none;
  max-height: 110px;
}
.chat-attach {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 6px;
  padding: 3px 8px;
  border-radius: 6px;
  background: #e7f1ff;
  color: #0a58ca;
  font-size: 0.8rem;
}
.chat-attach-btn {
  flex: none;
}
.chat-fade-enter-active,
.chat-fade-leave-active {
  transition: opacity 0.2s, transform 0.2s;
}
.chat-fade-enter-from,
.chat-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}
</style>
