// Central place that maps a filename (or a concept, like "tool role") to a
// Font Awesome icon class string. Every icon in the UI is rendered from
// the locally vendored ui/vendor/fontawesome/css/all.min.css - nothing here
// ever reaches out to a CDN.
import { FILE_ICON_MAP, DEFAULT_FILE_ICON } from "./config.js";
import { icon } from "./dom.js";

export function fileIconClass(name) {
  const ext = (name.split(".").pop() || "").toLowerCase();
  return FILE_ICON_MAP[ext] || DEFAULT_FILE_ICON;
}

export function fileIconHtml(name) {
  return icon(fileIconClass(name));
}

const ROLE_ICONS = {
  planner: "fa-solid fa-diagram-project",
  implementer: "fa-solid fa-code",
  reviewer: "fa-solid fa-magnifying-glass",
  tester: "fa-solid fa-vial",
  packager: "fa-solid fa-box-archive",
};
export function roleIconHtml(role) {
  return icon(ROLE_ICONS[role] || "fa-solid fa-circle-dot");
}

const TOOL_ICONS = {
  list_files: "fa-solid fa-folder-tree",
  read_file: "fa-solid fa-file-lines",
  write_file: "fa-solid fa-pen",
  run_command: "fa-solid fa-terminal",
  create_zip: "fa-solid fa-file-zipper",
};
export function toolIconHtml(tool) {
  return icon(TOOL_ICONS[tool] || "fa-solid fa-wrench");
}
