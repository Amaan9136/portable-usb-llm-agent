// Runs a task against /agent/stream and dispatches each Server-Sent
// Event to chat.js/pipeline.js. This is the module that makes "every
// action the AI takes streams into the UI live" actually true - every
// event the backend emits (tokens, tool calls, command output,
// reasoning/turn boundaries, perf) is handled here as it arrives, not
// batched up and shown only at the end.
import { el } from "./dom.js";
import * as api from "./api.js";
import { state } from "./state.js";
import { resetPipeline, advancePipelineTo, markAllDone, clearAll } from "./pipeline.js";
import {
  addUserMessage,
  addSystemMessage,
  startAgentMessage,
  addToolEvent,
  appendAgentToken,
  showPerf,
  finishAgentMessage,
} from "./chat.js";

export async function runTask(task) {
  if (state.running) return;
  if (!state.currentProject) {
    addSystemMessage("Open a project first so the agent has somewhere to work.");
    return;
  }
  state.running = true;
  el("btnSend").disabled = true;
  resetPipeline();
  addUserMessage(task);
  let agentDiv = null;

  const payload = {
    task: `Work inside the "${state.currentProject}" project folder (workspace/${state.currentProject}). ${task}`,
    project_name: state.currentProject,
    create_zip: el("createZip").checked,
    allow_commands: el("allowCommands").checked,
    allow_overwrite: el("allowOverwrite").checked,
    verbose_stream: state.verboseStream,
    testing_phase: state.testingPhase,
    backend: state.backend || null,
    model_name: state.backend === "ollama" ? state.modelName || null : null,
  };

  try {
    const res = await api.streamAgent(payload);
    if (!res.ok || !res.body) throw new Error("Stream request failed.");

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split("\n\n");
      buffer = chunks.pop();
      for (const chunk of chunks) {
        agentDiv = handleSseChunk(chunk, agentDiv);
      }
    }
  } catch (e) {
    addSystemMessage(`Connection error: ${e.message}`);
  } finally {
    state.running = false;
    el("btnSend").disabled = false;
  }
}

function handleSseChunk(chunk, agentDiv) {
  const lines = chunk.split("\n");
  let event = "message";
  let data = "";
  for (const line of lines) {
    if (line.startsWith("event:")) event = line.slice(6).trim();
    if (line.startsWith("data:")) data += line.slice(5).trim();
  }
  if (!data) return agentDiv;
  let payload;
  try {
    payload = JSON.parse(data);
  } catch {
    return agentDiv;
  }

  switch (event) {
    case "start":
      agentDiv = startAgentMessage({ backend: payload.backend, model: payload.model });
      break;
    case "turn_start":
      break;
    case "token":
      if (agentDiv) appendAgentToken(agentDiv, payload.text);
      break;
    case "tool_call_start":
      advancePipelineTo(payload.role);
      if (agentDiv) addToolEvent(agentDiv, payload.role, payload.tool, payload.arguments, null);
      break;
    case "tool_call_end":
      advancePipelineTo(payload.role);
      if (agentDiv) {
        addToolEvent(agentDiv, payload.role, payload.tool, payload.arguments, payload.result);
      }
      break;
    case "perf":
      if (agentDiv) showPerf(agentDiv, payload);
      break;
    case "warning":
      addSystemMessage(payload.message);
      break;
    case "error":
      addSystemMessage(payload.message);
      clearAll();
      break;
    case "final_answer":
      if (!agentDiv) agentDiv = startAgentMessage(null);
      finishAgentMessage(agentDiv, payload);
      markAllDone();
      break;
  }
  return agentDiv;
}
