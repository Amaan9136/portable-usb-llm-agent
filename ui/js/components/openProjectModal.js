export const html = `
<div id="openProjectModal" class="modal-overlay hidden">
  <div class="modal-card">
    <h3 class="font-display text-lg mb-4 flex items-center gap-2"><i class="fa-solid fa-folder-open text-cyan" aria-hidden="true"></i>Open a project</h3>
    <p class="text-dim text-xs mb-4 leading-relaxed">
      Paste the full path to a local folder. It's copied into the agent's sandboxed workspace &mdash;
      the original folder is never modified, and the agent can only ever touch files inside the sandbox.
    </p>
    <label class="block text-xs text-dim mb-1 font-mono uppercase tracking-wide">Folder path</label>
    <input id="importPathInput" type="text" placeholder="C:\\Users\\you\\Projects\\my-app" class="w-full bg-nebula/40 border border-line focus:border-cyan/60 outline-none rounded px-3 py-2 text-sm font-mono mb-3">
    <label class="block text-xs text-dim mb-1 font-mono uppercase tracking-wide">Project name (optional)</label>
    <input id="importNameInput" type="text" placeholder="my-app" class="w-full bg-nebula/40 border border-line focus:border-cyan/60 outline-none rounded px-3 py-2 text-sm font-mono mb-4">
    <div id="importError" class="text-xs text-magenta mb-3 hidden"></div>
    <div class="flex justify-end gap-2">
      <button id="btnCancelImport" class="px-3 py-1.5 text-xs rounded border border-line text-dim hover:text-starlight transition-colors">Cancel</button>
      <button id="btnConfirmImport" class="px-3 py-1.5 text-xs rounded bg-cyan/10 border border-cyan/50 text-cyan hover:bg-cyan/20 transition-colors">Import</button>
    </div>
  </div>
</div>`;
