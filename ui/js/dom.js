// Small DOM utilities used everywhere. Kept dependency-free so every
// other module can import from here without a cycle.
export const el = (id) => document.getElementById(id);

export function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s == null ? "" : String(s);
  return d.innerHTML;
}

export function cssEscape(s) {
  return String(s).replace(/["\\]/g, "\\$&");
}

/** Builds a Font Awesome <i> tag string, e.g. icon("fa-solid fa-folder"). */
export function icon(classes, extra = "") {
  return `<i class="${classes} ${extra}" aria-hidden="true"></i>`;
}
