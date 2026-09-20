from __future__ import annotations

import os
from contextlib import nullcontext
from typing import Any

from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()


def _client() -> Langfuse | None:
    if os.getenv("LANGFUSE_TRACING_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return None
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return None
    return Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=os.getenv("LANGFUSE_HOST", "http://localhost:3000"),
    )


def pipeline_observation(input_data: dict[str, Any]):
    """Return a Langfuse observation context, or a no-op when unconfigured."""
    client = _client()
    if client is None:
        return nullcontext()
    return client.start_as_current_observation(
        name="security-pipeline",
        as_type="chain",
        input=input_data,
    )


def record_pipeline_result(
    observation: Any,
    output_data: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    """Attach a result to an active observation and flush the SDK queue."""
    if hasattr(observation, "update"):
        observation.update(output=output_data, metadata=metadata)
    if hasattr(observation, "_client"):
        observation._client.flush()