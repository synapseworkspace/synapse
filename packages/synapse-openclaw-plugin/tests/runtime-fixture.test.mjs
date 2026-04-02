import assert from "node:assert/strict";
import test from "node:test";

import { DEFAULT_OPENCLAW_EVENTS, createSynapseOpenClawPlugin } from "../dist/index.js";

class RuntimeFixture {
  constructor() {
    this.hooks = new Map();
    this.tools = new Map();
  }

  on(eventName, handler) {
    this.hooks.set(eventName, handler);
  }

  register_tool(name, handler, description) {
    this.tools.set(name, { handler, description });
  }

  async emit(eventName, payload) {
    const handler = this.hooks.get(eventName);
    if (!handler) {
      throw new Error(`missing hook: ${eventName}`);
    }
    return handler(payload);
  }

  async callTool(toolName, ...args) {
    const entry = this.tools.get(toolName);
    if (!entry) {
      throw new Error(`missing tool: ${toolName}`);
    }
    return entry.handler(...args);
  }
}

class HookOnlyFixture {
  constructor() {
    this.hooks = new Map();
    this.tools = new Map();
  }

  register_hook(eventName, handler) {
    this.hooks.set(eventName, handler);
  }

  register_tool(name, handler, description) {
    this.tools.set(name, { handler, description });
  }
}

class ClientFixture {
  constructor() {
    this.projectId = "omega_demo";
    this.events = [];
    this.claims = [];
    this.statusUpdates = [];
  }

  capture(event) {
    this.events.push(event);
  }

  async proposeFact(claim) {
    this.claims.push(claim);
  }

  async listTasks(options = {}) {
    return [
      {
        id: "task-1",
        title: "Verify gate access policy",
        status: "todo",
        entity_key: options.entityKey ?? null
      }
    ];
  }

  async updateTaskStatus(taskId, options) {
    this.statusUpdates.push({ taskId, ...options });
    return { status: "ok", task_id: taskId, next_status: options.status };
  }
}

test("plugin attaches hooks and executes tool workflow", async () => {
  const runtime = new RuntimeFixture();
  const client = new ClientFixture();
  const plugin = createSynapseOpenClawPlugin(client, {
    searchKnowledge: async (query, limit, filters) => [{ query, limit, filters }],
    defaultAgentId: "openclaw_dispatcher",
    provenanceSecret: "plugin-contract-secret",
    provenanceKeyId: "plugin-key-1"
  });

  plugin.attach(runtime);

  assert.equal(runtime.hooks.size, DEFAULT_OPENCLAW_EVENTS.length);
  assert.ok(runtime.tools.has("synapse_search_wiki"));
  assert.ok(runtime.tools.has("synapse_propose_to_wiki"));
  assert.ok(runtime.tools.has("synapse_get_open_tasks"));
  assert.ok(runtime.tools.has("synapse_update_task_status"));

  await runtime.emit("tool:result", { sessionKey: "sess-1", output: "ok" });
  const hookCapture = client.events.find((item) => item.payload?.phase === "hook_event");
  assert.ok(hookCapture);
  assert.equal(hookCapture.session_id, "sess-1");

  const searchResult = await runtime.callTool("synapse_search_wiki", {
    query: "omega gate",
    limit: 4,
    filters: { entity_key: "bc_omega" }
  });
  assert.equal(Array.isArray(searchResult), true);
  assert.equal(searchResult[0].query, "omega gate");

  const proposeResult = await runtime.callTool("synapse_propose_to_wiki", {
    entity_key: "bc_omega",
    category: "access_policy",
    claim_text: "Gate is card-only after 10:00",
    source_id: "dialog-44",
    metadata: { source: "driver" }
  });
  assert.equal(proposeResult.status, "queued");
  assert.equal(client.claims.length, 1);
  assert.equal(client.claims[0].project_id, "omega_demo");
  assert.equal(client.claims[0].metadata.synapse_provenance.mode, "signed");
  assert.equal(client.claims[0].metadata.synapse_provenance.signature_alg, "hmac-sha256");
  assert.equal(client.claims[0].metadata.synapse_provenance.key_id, "plugin-key-1");
  assert.equal(typeof client.claims[0].metadata.synapse_provenance.signature, "string");
  assert.equal(client.claims[0].metadata.synapse_provenance.signature.length, 64);
  assert.equal(client.claims[0].evidence[0].provenance.signature, client.claims[0].metadata.synapse_provenance.signature);

  const tasksResult = await runtime.callTool("synapse_get_open_tasks", {
    entity_key: "bc_omega",
    limit: 10
  });
  assert.equal(tasksResult.tasks.length, 1);
  assert.equal(tasksResult.tasks[0].id, "task-1");

  const statusResult = await runtime.callTool("synapse_update_task_status", {
    task_id: "task-1",
    status: "in_progress",
    note: "driver confirmed gate card needed"
  });
  assert.equal(statusResult.status, "ok");
  assert.equal(client.statusUpdates.length, 1);
  assert.equal(client.statusUpdates[0].updatedBy, "openclaw_dispatcher");
});

test("plugin supports register_hook-only runtimes", () => {
  const runtime = new HookOnlyFixture();
  const client = new ClientFixture();
  const plugin = createSynapseOpenClawPlugin(client);

  plugin.attach(runtime, { registerTools: false, hookEvents: ["message:received"] });

  assert.equal(runtime.hooks.size, 1);
  assert.equal(runtime.hooks.has("message:received"), true);
});

test("plugin skips task tools without task API support", () => {
  const runtime = new RuntimeFixture();
  const client = {
    projectId: "omega_demo",
    capture() {},
    proposeFact() {}
  };

  const plugin = createSynapseOpenClawPlugin(client);
  plugin.attach(runtime);

  assert.equal(runtime.tools.has("synapse_propose_to_wiki"), true);
  assert.equal(runtime.tools.has("synapse_get_open_tasks"), false);
  assert.equal(runtime.tools.has("synapse_update_task_status"), false);
});
