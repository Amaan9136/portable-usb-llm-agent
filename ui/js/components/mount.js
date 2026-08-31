import { html as openProjectModalHtml } from "./openProjectModal.js";
import { html as cliModalHtml } from "./cliModal.js";
import { html as settingsModalHtml } from "./settingsModal.js";

export function mountModals() {
  const root = document.getElementById("modalRoot");
  root.innerHTML = openProjectModalHtml + cliModalHtml + settingsModalHtml;
}
