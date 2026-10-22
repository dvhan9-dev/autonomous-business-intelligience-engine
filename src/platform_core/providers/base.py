from typing import Protocol

from pydantic import BaseModel


class AgentRequest(BaseModel):
    task: str
    input_references: list[str]
    model: str | None = None


class AgentResponse(BaseModel):
    text: str
    provider: str
    model: str
    estimated_cost_usd: str


class AgentProvider(Protocol):
    """Future OpenAI/Anthropic/Gemini/Grok/OpenRouter/local adapters implement this port.

    Credentials belong in runtime bindings. This sprint never invokes a model provider.
    Provider output must not replace deterministic financial calculations.
    """

    def execute(self, request: AgentRequest) -> AgentResponse: ...
