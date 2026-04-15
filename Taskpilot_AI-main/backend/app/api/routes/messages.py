from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db_session
from app.models.db_models import AgentResult, AgentStatus, AgentStep, Message, MessageRole, UserSession
from app.schemas.messages import (
    AIResponse,
    AgentStepResponse,
    MessageRequest,
    MessageResponse,
    ScreenContextRequest,
    ScreenContextResponse,
    StructuredAIOutput,
    VoiceMessageRequest,
)
from app.services.orchestrator import TaskOrchestrator
from app.services.file_processor import FileProcessor
from app.services.chat_preprocessor import classify_query, greeting_reply, is_instant_greeting

router = APIRouter(tags=["messages"])
_orchestrator_instance: TaskOrchestrator | None = None
logger = logging.getLogger(__name__)


def _get_orchestrator() -> TaskOrchestrator:
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = TaskOrchestrator()
    return _orchestrator_instance


async def _get_session(session_id: str, db: AsyncSession) -> UserSession:
    result = await db.execute(select(UserSession).where(UserSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=getattr(message.role, "value", message.role),
        content=message.content,
        created_at=message.created_at,
    )


async def _get_latest_screen_context(session_id: str, db: AsyncSession) -> str | None:
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id, Message.role == MessageRole.system)
        .order_by(desc(Message.created_at))
        .limit(1)
    )
    message = result.scalar_one_or_none()
    return message.content if message else None


async def _get_recent_conversation_memory(session_id: str, db: AsyncSession, limit: int = 8) -> list[dict[str, str]]:
    """Fetch last N user/assistant messages for lightweight conversational memory."""
    result = await db.execute(
        select(Message)
        .where(
            Message.session_id == session_id,
            Message.role.in_([MessageRole.user, MessageRole.assistant]),
        )
        .order_by(desc(Message.created_at))
        .limit(limit)
    )
    recent = list(reversed(result.scalars().all()))
    return [
        {
            "role": getattr(item.role, "value", str(item.role)),
            "content": item.content,
        }
        for item in recent
    ]


async def _persist_agent_steps(
    session_id: str,
    steps: list[AgentStepResponse],
    db: AsyncSession,
    input_text: str,
) -> None:
    for step in steps:
        db.add(
            AgentStep(
                session_id=session_id,
                name=step.name,
                status=AgentStatus.complete,
                input_text=input_text,
                output_text=step.output,
            )
        )


async def _run_orchestration_with_retry(
    orchestrator: TaskOrchestrator,
    *,
    user_input: str,
    screen_context: str | None,
    attachments: list[dict] | None,
    conversation_memory: list[dict[str, str]],
    routing: dict,
    session_id: str,
    max_attempts: int = 2,
) -> tuple[object | None, str | None]:
    """Run orchestration with timeout + retry so transient overload does not fail the user request."""
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        attempt_timeout = max(35, min(settings.orchestration_timeout_seconds, 45))
        try:
            orchestration = await asyncio.wait_for(
                orchestrator.run(
                    user_input,
                    screen_context=screen_context,
                    attachments=attachments,
                    conversation_history=conversation_memory,
                    routing_hint=routing,
                ),
                timeout=attempt_timeout,
            )
            return orchestration, None
        except asyncio.TimeoutError as exc:
            last_error = exc
            logger.warning(
                "Chat orchestration timed out",
                extra={"session_id": session_id, "attempt": attempt, "max_attempts": max_attempts},
            )
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            err_text = str(exc).lower()
            if "429" in err_text or "quota" in err_text or "rate limit" in err_text:
                logger.warning(
                    "Skipping retry due to upstream rate limit",
                    extra={"session_id": session_id, "attempt": attempt},
                )
                break
            logger.exception(
                "Chat orchestration attempt failed",
                extra={"session_id": session_id, "attempt": attempt, "max_attempts": max_attempts},
            )

        if attempt < max_attempts:
            await asyncio.sleep(0.35 * attempt)

    if isinstance(last_error, asyncio.TimeoutError):
        return None, "AI processing timed out after retries."
    return None, "AI processing failed after retries."


def _safe_response_text(orchestration, failure_reason: str | None = None) -> str:
    """Ensure assistant response is always non-empty for frontend rendering."""
    if orchestration:
        final_response = (orchestration.final_response or "").strip()
        if final_response:
            return final_response

        structured = orchestration.structured or {}
        for key in ("report", "analysis", "fetched_context"):
            value = structured.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        summary = (orchestration.summary or "").strip()
        if summary:
            return summary

    if failure_reason:
        return "Here is a concise response. Ask for a deeper or more current update anytime."

    return "Here is a concise response based on available context. Ask for a deeper or more current update anytime."


@router.post("/messages", response_model=AIResponse)
async def send_message(
    payload: MessageRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AIResponse:
    session = await _get_session(payload.session_id, db)
    screen_context = await _get_latest_screen_context(session.id, db)
    conversation_memory = await _get_recent_conversation_memory(session.id, db)

    # Fast-path greeting: respond instantly with no LLM/agent call.
    if is_instant_greeting(payload.content):
        user_message = Message(
            session_id=session.id,
            role=MessageRole.user,
            content=payload.content,
        )
        db.add(user_message)
        await db.commit()

        assistant_message = Message(
            session_id=session.id,
            role=MessageRole.assistant,
            content=greeting_reply(),
        )
        db.add(assistant_message)
        db.add(
            AgentResult(
                session_id=session.id,
                status=AgentStatus.complete,
                summary="Instant greeting response.",
            )
        )
        session.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(assistant_message)

        return AIResponse(
            session_id=session.id,
            message=_message_response(assistant_message),
            agent_summary="Instant greeting response.",
            structured=None,
            steps=[],
        )

    routing = classify_query(payload.content)

    user_message = Message(
        session_id=session.id,
        role=MessageRole.user,
        content=payload.content,
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    # Process attachments if present (in parallel so multiple files don't block each other)
    processed_attachments: list[dict] = []
    if payload.attachments:
        file_processor = FileProcessor()
        async def _process_one(attachment):
            return await asyncio.wait_for(
                file_processor.process_attachment(attachment.mime_type, attachment.data),
                timeout=12,
            )

        processed_results = await asyncio.gather(
            *[_process_one(attachment) for attachment in payload.attachments],
            return_exceptions=True,
        )
        for result in processed_results:
            if isinstance(result, Exception):
                processed_attachments.append(
                    {
                        "type": "error",
                        "content": "Could not process one attachment in time.",
                        "metadata": {"error": str(result)},
                    }
                )
            else:
                processed_attachments.append(result)

    orchestrator = _get_orchestrator()

    orchestration = None
    failure_reason = None

    orchestration, failure_reason = await _run_orchestration_with_retry(
        orchestrator,
        user_input=payload.content,
        screen_context=screen_context,
        attachments=processed_attachments if processed_attachments else None,
        conversation_memory=conversation_memory,
        routing=routing,
        session_id=session.id,
    )

    response_text = _safe_response_text(orchestration, failure_reason)

    assistant_message = Message(
        session_id=session.id,
        role=MessageRole.assistant,
        content=response_text,
    )
    db.add(assistant_message)

    steps: list[AgentStepResponse] = []
    summary = failure_reason or ""

    if orchestration:
        steps = [
            AgentStepResponse(
                name=step.name,
                status=step.status,
                output=step.output,
                details={k: str(v) for k, v in step.details.items()} if step.details else None,
            )
            for step in orchestration.steps
        ]
        await _persist_agent_steps(session.id, steps, db, payload.content)
        summary = orchestration.summary

    db.add(
        AgentResult(
            session_id=session.id,
            status=AgentStatus.complete if orchestration else AgentStatus.failed,
            summary=summary,
        )
    )

    session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(assistant_message)

    structured = StructuredAIOutput(**orchestration.structured) if orchestration else None

    return AIResponse(
        session_id=session.id,
        message=_message_response(assistant_message),
        agent_summary=summary or None,
        structured=structured,
        steps=steps,
    )


@router.post("/voice", response_model=AIResponse)
async def send_voice_message(
    payload: VoiceMessageRequest,
    db: AsyncSession = Depends(get_db_session),
) -> AIResponse:
    session = await _get_session(payload.session_id, db)
    screen_context = payload.screen_context or await _get_latest_screen_context(session.id, db)
    conversation_memory = await _get_recent_conversation_memory(session.id, db)

    user_message = Message(
        session_id=session.id,
        role=MessageRole.user,
        content=payload.transcript,
    )
    db.add(user_message)
    await db.commit()
    await db.refresh(user_message)

    orchestrator = _get_orchestrator()
    routing = classify_query(payload.transcript)

    orchestration = None
    failure_reason = None

    orchestration, failure_reason = await _run_orchestration_with_retry(
        orchestrator,
        user_input=payload.transcript,
        screen_context=screen_context,
        attachments=None,
        conversation_memory=conversation_memory,
        routing=routing,
        session_id=session.id,
    )

    response_text = _safe_response_text(orchestration, failure_reason)

    assistant_message = Message(
        session_id=session.id,
        role=MessageRole.assistant,
        content=response_text,
    )
    db.add(assistant_message)

    steps: list[AgentStepResponse] = []
    summary = failure_reason or ""

    if orchestration:
        steps = [
            AgentStepResponse(
                name=step.name,
                status=step.status,
                output=step.output,
                details={k: str(v) for k, v in step.details.items()} if step.details else None,
            )
            for step in orchestration.steps
        ]
        await _persist_agent_steps(session.id, steps, db, payload.transcript)
        summary = orchestration.summary

    db.add(
        AgentResult(
            session_id=session.id,
            status=AgentStatus.complete if orchestration else AgentStatus.failed,
            summary=summary,
        )
    )

    session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(assistant_message)

    structured = StructuredAIOutput(**orchestration.structured) if orchestration else None

    return AIResponse(
        session_id=session.id,
        message=_message_response(assistant_message),
        agent_summary=summary or None,
        structured=structured,
        steps=steps,
    )


@router.post("/screen-context", response_model=ScreenContextResponse)
async def store_screen_context(
    payload: ScreenContextRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ScreenContextResponse:
    session = await _get_session(payload.session_id, db)

    context_payload = payload.context
    if payload.metadata:
        metadata = ", ".join(f"{key}={value}" for key, value in payload.metadata.items())
        context_payload = f"{payload.context}\nMetadata: {metadata}"

    system_message = Message(
        session_id=session.id,
        role=MessageRole.system,
        content=context_payload,
    )
    db.add(system_message)
    session.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(system_message)

    return ScreenContextResponse(session_id=session.id, message=_message_response(system_message))
