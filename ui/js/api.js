// Every network call to the agent server lives here, so other modules
// never construct a fetch() call directly - they call a named function
// and get back either parsed JSON or a thrown Error.
import { apiUrl } from "./state.js";

async function getJson(path) {
  const res = await fetch(apiUrl(path));
  if (!res.ok) throw new Error(`${path} -> HTTP ${res.status}`);
  return res.json();
}

export function health() {
  return getJson("/health");
}

export function models() {
  return getJson("/models");
}

export async function selectModel(backend, modelName) {
  const res = await fetch(apiUrl("/models/select"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ backend, model_name: modelName || null }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Could not switch model.");
  return data;
}

export function projects() {
  return getJson("/projects");
}

export async function importProject(sourcePath, projectName) {
  const res = await fetch(apiUrl("/projects/import"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source_path: sourcePath, project_name: projectName || null }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Import failed.");
  return data;
}

export function tree(relativePath) {
  return getJson(`/tree?relative_path=${encodeURIComponent(relativePath)}`);
}

export function readFile(relativePath) {
  return getJson(`/file?relative_path=${encodeURIComponent(relativePath)}`);
}

export function artifactDownloadUrl(relativePath) {
  return apiUrl(`/workspace/download?relative_path=${encodeURIComponent(relativePath)}`);
}

export function explorerDownloadUrl(relativePath) {
  return apiUrl(`/explorer/download?relative_path=${encodeURIComponent(relativePath)}`);
}

/** Kicks off a streaming agent run. Returns the fetch Response so the
 * caller can read its body as an SSE stream (see streaming.js). */
export function streamAgent(payload) {
  return fetch(apiUrl("/agent/stream"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}