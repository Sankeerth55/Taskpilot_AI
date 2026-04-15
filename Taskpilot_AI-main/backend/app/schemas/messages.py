from datetime import datetime
from pydantic import BaseModel, Field


class AttachmentData(BaseModel):
    """Attachment data for file uploads."""
    mime_type: str
    data: str  # Base64 encoded
    filename: str | None = None


class MessageRequest(BaseModel):
    session_id: str
    content: str
    attachments: list[AttachmentData] | None = None  # Optional for backward compatibility


class VoiceMessageRequest(BaseModel):
    session_id: str
    transcript: str
    screen_context: str | None = None


class ScreenContextRequest(BaseModel):
    session_id: str
    context: str
    metadata: dict[str, str] | None = None


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


class MessageListResponse(BaseModel):
    messages: list[MessageResponse] = Field(default_factory=list)


class AgentStepResponse(BaseModel):
    name: str
    status: str
    output: str
    details: dict[str, str] | None = None


class StructuredAIOutput(BaseModel):
    fetched_context: str | None = None
    analysis: str | None = None
    plan: list[str] = Field(default_factory=list)
    report: str | None = None


class AIResponse(BaseModel):
    session_id: str
    message: MessageResponse
    agent_summary: str | None = None
    structured: StructuredAIOutput | None = None
    steps: list[AgentStepResponse] = Field(default_factory=list)


class ScreenContextResponse(BaseModel):
    session_id: str
    message: MessageResponse
