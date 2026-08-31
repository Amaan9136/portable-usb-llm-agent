// Shared constants. No state or DOM access here - just fixed values other
// modules import, so changing a constant never means hunting through the
// rest of the codebase.
export const ROLE_ORDER = ["planner", "implementer", "reviewer", "tester", "packager"];

export const FILE_ICON_MAP = {
  py: "fa-brands fa-python",
  js: "fa-brands fa-js",
  ts: "fa-brands fa-js",
  jsx: "fa-brands fa-react",
  tsx: "fa-brands fa-react",
  json: "fa-solid fa-code",
  md: "fa-solid fa-file-lines",
  html: "fa-brands fa-html5",
  css: "fa-brands fa-css3-alt",
  txt: "fa-solid fa-file-lines",
  yml: "fa-solid fa-gear",
  yaml: "fa-solid fa-gear",
  bat: "fa-brands fa-windows",
  ps1: "fa-brands fa-windows",
  sh: "fa-solid fa-terminal",
  gitignore: "fa-brands fa-git-alt",
  env: "fa-solid fa-gear",
  toml: "fa-solid fa-gear",
  cfg: "fa-solid fa-gear",
  ini: "fa-solid fa-gear",
  png: "fa-solid fa-image",
  jpg: "fa-solid fa-image",
  jpeg: "fa-solid fa-image",
  svg: "fa-solid fa-image",
  gif: "fa-solid fa-image",
  zip: "fa-solid fa-file-zipper",
  pdf: "fa-solid fa-file-pdf",
};
export const DEFAULT_FILE_ICON = "fa-solid fa-file";

// Settings that persist across sessions, with their localStorage keys and
// hard-coded fallback defaults. The agent's own /health response
// (testing_phase_default / verbose_stream_default) is used instead of
// these fallbacks whenever it is reachable - see settings.js.
export const SETTINGS_STORAGE_KEYS = {
  verboseStream: "settings.verboseStream",
  testingPhase: "settings.testingPhase",
  backend: "settings.backend",
  modelName: "settings.modelName",
};
