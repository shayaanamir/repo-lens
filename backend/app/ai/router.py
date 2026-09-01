import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.chat_service import answer_chat_question
from app.ai.errors import AIUnavailableError
from app.ai.explain_service import FileNotFoundForExplainError, explain_file
from app.ai.interview_prep_service import generate_interview_prep
from app.ai.schemas import (
    ChatRequest,
    ChatResponse,
    ExplainResponse,
    InterviewPrepRequest,
    InterviewPrepResponse,
    QAOut,
    SourceOut,
)
from app.core.config import settings
from app.core.db import get_db
from app.repo.models import Repository

router = APIRouter(prefix="/repositories", tags=["ai"])


@router.post("/{repository_id}/chat", response_model=ChatResponse)
async def chat_with_repository(
    repository_id: uuid.UUID, payload: ChatRequest, db: AsyncSession = Depends(get_db)
) -> ChatResponse:
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        result = await answer_chat_question(db, repository, payload.question)
    except AIUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI chat is currently unavailable: {e}") from e

    return ChatResponse(
        answer=result.answer,
        sources=[SourceOut(path=s.path, start_line=s.start_line, end_line=s.end_line) for s in result.sources],
    )


@router.post("/{repository_id}/files/{file_path:path}/explain", response_model=ExplainResponse)
async def explain_repository_file(
    repository_id: uuid.UUID, file_path: str, db: AsyncSession = Depends(get_db)
) -> ExplainResponse:
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    repo_dir = Path(settings.repo_storage_dir) / str(repository_id)

    try:
        result = await explain_file(db, repository, repo_dir, file_path)
    except FileNotFoundForExplainError as e:
        raise HTTPException(status_code=404, detail="File not found") from e
    except AIUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"AI explanation is currently unavailable: {e}") from e

    return ExplainResponse(
        explanation=result.explanation,
        sources=[SourceOut(path=s.path, start_line=s.start_line, end_line=s.end_line) for s in result.sources],
    )


@router.post("/{repository_id}/interview-prep", response_model=InterviewPrepResponse)
async def get_interview_prep(
    repository_id: uuid.UUID,
    payload: InterviewPrepRequest,
    db: AsyncSession = Depends(get_db),
) -> InterviewPrepResponse:
    repository = await db.get(Repository, repository_id)
    if repository is None:
        raise HTTPException(status_code=404, detail="Repository not found")

    try:
        result = await generate_interview_prep(db, repository, payload.context)
    except AIUnavailableError as e:
        raise HTTPException(
            status_code=503, detail=f"Interview prep is currently unavailable: {e}"
        ) from e

    return InterviewPrepResponse(
    pitch=result.pitch,
    talking_points=result.talking_points,
    questions=[QAOut(question=q.question, answer=q.answer) for q in result.questions],
    grounded_in=[SourceOut(path=s.path, start_line=s.start_line, end_line=s.end_line) for s in result.grounded_in],
)