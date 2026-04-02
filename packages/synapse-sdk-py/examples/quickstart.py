from __future__ import annotations

from synapse_sdk import SynapseConfig, init

synapse = init(
    SynapseConfig(
        api_url="http://localhost:8080",
        project_id="water_delivery_logistics",
    )
)

synapse.capture(
    event_type="agent_message",
    payload={"text": "Omega gate now requires access cards"},
    tags=["demo", "omega"],
)

synapse.flush()
print("Flushed one event to Synapse API")
