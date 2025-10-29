# agent_core/config/schema.py
from typing import Sequence

from pydantic import BaseModel, Field, ConfigDict


class AgentConfig(BaseModel):
    id: str = Field(pattern=r"^[A-Z0-9_]+$")
    name: str
    provider: str = "openai"
    model: str = "gpt-4o"
    langfuse_prompt_key: str
    text_format: str | None = None
    assistant_id: str | None = None
    instructions: str | None = None
    vector_store_ids: list[str] | None = Field(
        default=None,
        description="Logical IDs of vector stores to be queried alongside the LLM"
    )
    tools: Sequence[str] | None = None
    temperature: float | None = None
    top_p: float | None = None

    model_config = ConfigDict(
        frozen=True,  # makes instances hashable & truly immutable
        populate_by_name=True,
    )
