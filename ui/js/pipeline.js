// The planner -> implementer -> reviewer -> tester -> packager status
// bar at the top of the chat pane.
import { el } from "./dom.js";
import { ROLE_ORDER } from "./config.js";

const pipelineBar = el("pipelineBar");

export function setRoleState(role, status) {
  const node = pipelineBar.querySelector(`[data-role="${role}"]`);
  if (!node) return;
  node.classList.remove("role-active", "role-done");
  if (status === "active") node.classList.add("role-active");
  if (status === "done") node.classList.add("role-done");
}

export function resetPipeline() {
  pipelineBar.querySelectorAll("[data-role]").forEach((n) => {
    n.classList.remove("role-active", "role-done");
  });
}

export function advancePipelineTo(role) {
  const idx = ROLE_ORDER.indexOf(role);
  ROLE_ORDER.forEach((r, i) => {
    if (i < idx) setRoleState(r, "done");
    else if (i === idx) setRoleState(r, "active");
    else setRoleState(r, "");
  });
}

export function markAllDone() {
  ROLE_ORDER.forEach((r) => setRoleState(r, "done"));
}

export function clearAll() {
  ROLE_ORDER.forEach((r) => setRoleState(r, ""));
}
