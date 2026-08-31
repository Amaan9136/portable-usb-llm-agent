// Generic open/close for any .modal-overlay element by id. Individual
// modals' own field-population logic lives in the module that owns that
// modal (settings.js, models.js, main.js for the import/CLI modals).
//
// Only one modal is ever visible at a time. Without this, opening a
// second modal while a first was still open (e.g. a stray double click)
// stacked both overlays at the same z-index - the top one ate every
// click, leaving the one underneath's buttons completely unresponsive.
import { el } from "./dom.js";

export function closeAllModals() {
  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.classList.add("hidden");
  });
}

export function openModal(id) {
  closeAllModals();
  el(id).classList.remove("hidden");
}
export function closeModal(id) {
  el(id).classList.add("hidden");
}

export function wireOverlayDismiss() {
  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (e) => {
      if (e.target === overlay) overlay.classList.add("hidden");
    });
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllModals();
  });
}