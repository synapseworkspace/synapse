import { init } from "../src/index.js";

async function main() {
  const synapse = init({
    apiUrl: "http://localhost:8080",
    projectId: "water_delivery_logistics"
  });

  synapse.capture({
    event_type: "agent_message",
    payload: { text: "Omega gate now requires access cards" },
    observed_at: new Date().toISOString(),
    tags: ["demo", "omega"]
  });

  await synapse.flush();
  console.log("Flushed one event to Synapse API");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
