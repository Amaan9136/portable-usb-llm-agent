// Generic open/close for any .modal-overlay element by id. Individual
// modals' own field-population logic lives in the module that owns that
// modal (settings.js, models.js, main.js for the import/CLI modals).
import { el } from "./dom.js";

export function openModal(id) {
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
}
