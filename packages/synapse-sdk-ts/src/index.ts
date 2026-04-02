import { Synapse } from "./client.js";
import type { SynapseConfig } from "./types.js";

export * from "./types.js";
export * from "./client.js";
export * from "./mcp.js";
export * from "./openclaw.js";
export * from "./telemetry.js";
export * from "./transports/http.js";

/** @deprecated Use `new Synapse(config)` directly. */
export function init(config: SynapseConfig): Synapse {
  return new Synapse(config);
}

export function fromEnv(overrides: Partial<SynapseConfig> = {}): Synapse {
  return Synapse.fromEnv(overrides);
}
