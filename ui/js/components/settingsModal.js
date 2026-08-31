export const html = `
<div id="settingsModal" class="modal-overlay hidden">
  <div class="modal-card !max-w-lg">
    <h3 class="font-display text-lg mb-4 flex items-center gap-2"><i class="fa-solid fa-gear text-cyan" aria-hidden="true"></i>Settings</h3>

    <label class="block text-xs text-dim mb-1 font-mono uppercase tracking-wide">Agent server URL</label>
    <input id="agentUrlInput" type="text" placeholder="http://127.0.0.1:8787" class="w-full bg-nebula/40 border border-line focus:border-cyan/60 outline-none rounded px-3 py-2 text-sm font-mono mb-5">

    <div class="mb-1 text-xs text-dim font-mono uppercase tracking-wide flex items-center gap-1.5">
      <i class="fa-solid fa-microchip" aria-hidden="true"></i> Model
    </div>
    <p class="text-dim text-xs mb-2 leading-relaxed">
      Choose the built-in portable model, or (optional) any model Ollama reports installed &mdash;
      local or cloud. Ollama is entirely opt-in; the portable flow keeps working either way.
    </p>
    <select id="modelSelect" class="model-select mb-2">
      <option value="">Loading models&hellip;</option>
    </select>
    <div class="flex items-center gap-2 mb-1">
      <button id="btnApplyModel" class="px-3 py-1.5 text-xs rounded bg-cyan/10 border border-cyan/50 text-cyan hover:bg-cyan/20 transition-colors">Use this model</button>
      <button id="btnRefreshModels" class="px-3 py-1.5 text-xs rounded border border-line text-dim hover:text-starlight transition-colors">
        <i class="fa-solid fa-rotate" aria-hidden="true"></i>
      </button>
    </div>
    <div id="modelStatus"></div>

    <div class="mt-5 mb-1 text-xs text-dim font-mono uppercase tracking-wide">Streaming &amp; logging</div>
    <div class="settings-toggle-row">
      <div>
        <div class="settings-toggle-label"><i class="fa-solid fa-tower-broadcast text-cyan" aria-hidden="true"></i>Verbose event streaming</div>
        <div class="settings-toggle-caption">Show every tool call, command, and reasoning step live in the chat as the agent works, not just the final answer.</div>
      </div>
      <label class="switch">
        <input type="checkbox" id="verboseStreamToggle">
        <span class="switch-track"></span>
      </label>
    </div>
    <div class="settings-toggle-row">
      <div>
        <div class="settings-toggle-label"><i class="fa-solid fa-vial text-cyan" aria-hidden="true"></i>Testing phase</div>
        <div class="settings-toggle-caption">Let the tester role run tests (pytest/npm/etc.) after changes. Turning this off also unchecks "Allow commands" for new runs.</div>
      </div>
      <label class="switch">
        <input type="checkbox" id="testingPhaseToggle">
        <span class="switch-track"></span>
      </label>
    </div>

    <div class="flex justify-end gap-2 mt-5">
      <button id="btnCancelSettings" class="px-3 py-1.5 text-xs rounded border border-line text-dim hover:text-starlight transition-colors">Cancel</button>
      <button id="btnSaveSettings" class="px-3 py-1.5 text-xs rounded bg-cyan/10 border border-cyan/50 text-cyan hover:bg-cyan/20 transition-colors">Save</button>
    </div>
  </div>
</div>`;
