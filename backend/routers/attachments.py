"""Attachment upload, download, and delete API routes."""

import os
import uuid
from pathlib import Path

import filetype
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from backend import schemas
from backend.auth import get_current_user
from backend.config import UPLOAD_DIR, ALLOWED_CONTENT_TYPES, MAX_UPLOAD_SIZE
from backend.database import get_db
from backend.models import User, Contract, Attachment

router = APIRouter(tags=["attachments"])

# Map content types to extensions for filetype validation
ALLOWED_EXTENSIONS = {"pdf", "doc", "docx"}


def _get_attachment_or_404(db: Session, attachment_id: int) -> Attachment:
    """Fetch an attachment by ID or raise 404."""
    att = db.query(Attachment).filter(Attachment.id == attachment_id).first()
    if att is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )
    return att


@router.post(
    "/contracts/{contract_id}/attachments",
    response_model=schemas.AttachmentResponse,
    status_code=201,
)
async def upload_attachment(
    contract_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload a file attachment to a contract.

    Validates file type via magic number detection (filetype library).
    Only accepts PDF, DOC, and DOCX files.
    """
    # Check contract exists and is accessible
    contract = db.query(Contract).filter(Contract.id == contract_id).first()
    if contract is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found"
        )
    if current_user.role != "admin" and contract.creator_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contract not found"
        )

    # Read file content
    contents = await file.read()
    if len(contents) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024*1024)} MB.",
        )

    # Validate file type via magic number detection
    kind = filetype.guess(contents)
    if kind is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot determine file type. Only PDF, DOC, and DOCX files are accepted.",
        )

    ext = kind.extension
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '*.{ext}' is not allowed. Only PDF, DOC, and DOCX files are accepted.",
        )

    # Also check extension as a secondary validation
    original_ext = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
    if original_ext and original_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File extension '*.{original_ext}' is not allowed. Only PDF, DOC, and DOCX accepted.",
        )

    # Unique filename to prevent collisions
    safe_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(UPLOAD_DIR, safe_name)

    # Write to disk
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(contents)

    # Create DB record
    attachment = Attachment(
        filename=safe_name,
        original_name=file.filename or safe_name,
        file_path=file_path,
        file_size=len(contents),
        content_type=kind.mime,
        contract_id=contract_id,
        uploader_id=current_user.id,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)

    return schemas.AttachmentResponse.model_validate(attachment)


@router.get("/attachments/{attachment_id}")
def download_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Download an attachment by ID."""
    att = _get_attachment_or_404(db, attachment_id)

    # Access check — user must own the contract or be admin
    contract = db.query(Contract).filter(Contract.id == att.contract_id).first()
    if current_user.role != "admin" and (
        contract is None or contract.creator_id != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    if not os.path.isfile(att.file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk"
        )

    encoded_filename = quote(att.original_name)
    return FileResponse(
        path=att.file_path,
        filename=att.original_name,
        media_type=att.content_type,
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        },
    )


@router.delete("/attachments/{attachment_id}", response_model=schemas.MessageResponse)
def delete_attachment(
    attachment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delete an attachment."""
    att = _get_attachment_or_404(db, attachment_id)

    # Access check — user must own the attachment or be admin
    if current_user.role != "admin" and att.uploader_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found"
        )

    # Remove file from disk
    if os.path.isfile(att.file_path):
        os.remove(att.file_path)

    db.delete(att)
    db.commit()
    return schemas.MessageResponse(message="Attachment deleted")
