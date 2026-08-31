// The settings modal's toggles: verbose event streaming (show every tool
// call/command/reasoning step live) and testing phase (whether the
// tester role's run_command calls happen by default). Each toggle has a
// one-line caption explaining what it does, per the brief.
import { el } from "./dom.js";
import { state, setSetting } from "./state.js";
import { onHealth } from "./connection.js";

export function initSettingsToggles() {
  const verboseToggle = el("verboseStreamToggle");
  const testingToggle = el("testingPhaseToggle");

  verboseToggle.checked = state.verboseStream;
  testingToggle.checked = state.testingPhase;

  verboseToggle.addEventListener("change", () => {
    setSetting("verboseStream", verboseToggle.checked);
  });
  testingToggle.addEventListener("change", () => {
    setSetting("testingPhase", testingToggle.checked);
    // Testing phase also gates whether "Allow commands" is pre-checked
    // for new runs, since the tester role only runs when both are true.
    if (!testingToggle.checked) el("allowCommands").checked = false;
  });

  // Adopt the agent's own defaults the first time we hear from it, but
  // never override a value the user has explicitly chosen before.
  onHealth((data) => {
    if (!state.hasStoredVerbose && typeof data.verbose_stream_default === "boolean") {
      state.verboseStream = data.verbose_stream_default;
      verboseToggle.checked = state.verboseStream;
    }
    if (!state.hasStoredTesting && typeof data.testing_phase_default === "boolean") {
      state.testingPhase = data.testing_phase_default;
      testingToggle.checked = state.testingPhase;
    }
  });
}