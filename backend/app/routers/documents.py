import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.rate_limiter import upload_rate_limiter
from app.core.idempotency import IdempotencyService
from app.core.cache import CacheService
from app.models.user import User
from app.schemas.document import DocumentRead, DocumentSummary
from app.repositories.document_repo import DocumentRepository
from app.services.document_service import DocumentService
from app.services.summary_service import SummaryService

router = APIRouter(prefix="/documents", tags=["Documents"])


@router.post(
    "",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="Uploads a PDF, TXT, or MD file. Processes parsing and vector embeddings in the background.",
    dependencies=[Depends(upload_rate_limiter)],
)
async def upload_document(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    idemp_key = IdempotencyService.get_key_from_request(request)

    # 1. Check idempotency cache
    if idemp_key:
        cached = await IdempotencyService.get_cached_response(
            user_id=current_user.id,
            key=idemp_key,
            db=db,
        )
        if cached:
            status_code, body = cached
            response.status_code = status_code
            return body

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty.")

    try:
        doc, is_duplicate = await DocumentService.upload_document(
            db=db,
            user_id=current_user.id,
            filename=file.filename or "uploaded_file",
            file_bytes=file_bytes,
            mime_type=file.content_type or "application/octet-stream",
        )
    except ValueError as err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(err))

    # If it is not duplicate and status is uploaded, enqueue background embedding task
    if not is_duplicate and doc.status == "uploaded":
        background_tasks.add_task(
            DocumentService.process_document_background,
            document_id=doc.id,
            user_id=current_user.id,
            storage_path=doc.storage_path,
            filename=doc.filename,
        )

    # Return document representation
    doc_read = DocumentRead.model_validate(doc)

    # Record idempotency key response if present
    if idemp_key:
        await IdempotencyService.record_response(
            user_id=current_user.id,
            key=idemp_key,
            request_hash=doc.content_hash,
            status_code=status.HTTP_201_CREATED,
            response_body=doc_read.model_dump(mode="json"),
            db=db,
        )

    return doc_read


@router.get(
    "",
    response_model=List[DocumentRead],
    summary="List documents",
    description="Lists documents owned by current authenticated user.",
)
async def list_documents(
    limit: int = 50,
    status_filter: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    docs = await DocumentRepository.list_documents(
        db=db,
        user_id=current_user.id,
        limit=limit,
        status_filter=status_filter,
    )
    return docs


@router.get(
    "/{document_id}",
    response_model=DocumentRead,
    summary="Get document details & processing status",
)
async def get_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await DocumentRepository.get_by_id(db=db, document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return doc


@router.delete(
    "/{document_id}",
    summary="Delete document",
    description="Deletes document, cascading chunks, and invalidates RAG query cache.",
)
async def delete_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = await DocumentRepository.delete_document(
        db=db,
        document_id=document_id,
        user_id=current_user.id,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    # Bump user docs_version to invalidate stale query caches
    await CacheService.invalidate_user_docs_cache(user_id=str(current_user.id))

    return {"message": "Document deleted successfully"}


@router.post(
    "/{document_id}/summary",
    response_model=DocumentSummary,
    summary="Structured summary of a document (FR-I1)",
)
async def get_document_summary(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    doc = await DocumentRepository.get_by_id(db=db, document_id=document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    try:
        with open(doc.storage_path, "rb") as f:
            file_bytes = f.read()
        from app.services.document_parser import DocumentParser
        pages = DocumentParser.extract_text(file_bytes=file_bytes, filename=doc.filename)
        full_text = "\n\n".join(p.text for p in pages)
        summary = await SummaryService.generate_summary(full_text)
        return summary
    except Exception as err:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to generate summary: {str(err)}")
