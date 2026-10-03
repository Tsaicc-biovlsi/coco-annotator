// Bootstrap 5 modal helpers (replace the jQuery `$(el).modal(...)` API).
import { Modal } from "bootstrap";

function element(target) {
  return typeof target === "string" ? document.querySelector(target) : target;
}

export function showModal(target) {
  let el = element(target);
  if (el) Modal.getOrCreateInstance(el).show();
}

export function hideModal(target) {
  let el = element(target);
  if (el) Modal.getOrCreateInstance(el).hide();
}

export function onModalHidden(target, handler) {
  let el = element(target);
  if (el) el.addEventListener("hidden.bs.modal", handler);
}
