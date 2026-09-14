"""Explicit service-owned MCP content; ordinary dictionaries remain business data."""

from mcp.types import ContentBlock
from pydantic import BaseModel, ConfigDict, TypeAdapter

CONTENT_BLOCK = TypeAdapter(ContentBlock)


class ServiceContent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    content: list[ContentBlock]

    def blocks(self) -> list[dict]:
        return [
            block.model_dump(mode="json", by_alias=True, exclude_none=True)
            for block in self.content
        ]
