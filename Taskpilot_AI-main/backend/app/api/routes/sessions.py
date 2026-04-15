from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models.db_models import Message, SessionStatus, UserSession
from app.schemas.messages import MessageResponse
from app.schemas.sessions import SessionCreateRequest, SessionDetailResponse, SessionListResponse, SessionResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _message_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=getattr(message.role, "value", message.role),
        content=message.content,
        created_at=message.created_at,
    )


@router.post("", response_model=SessionResponse)
async def create_session(
    payload: SessionCreateRequest,
    db: AsyncSession = Depends(get_db_session),
) -> SessionResponse:
    session = UserSession(title=payload.title, status=SessionStatus.active)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionResponse(
        id=session.id,
        title=session.title,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get("", response_model=SessionListResponse)
async def list_sessions(db: AsyncSession = Depends(get_db_session)) -> SessionListResponse:
    result = await db.execute(select(UserSession).order_by(UserSession.updated_at.desc()))
    sessions = result.scalars().all()
    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=item.id,
                title=item.title,
                status=item.status,
                created_at=item.created_at,
                updated_at=item.updated_at,
            )
            for item in sessions
        ]
    )


@router.get("/{session_id}", response_model=SessionDetailResponse)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db_session)) -> SessionDetailResponse:
    result = await db.execute(select(UserSession).where(UserSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    message_result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.asc())
    )
    messages = message_result.scalars().all()

    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        status=session.status,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[_message_response(message) for message in messages],
    )
