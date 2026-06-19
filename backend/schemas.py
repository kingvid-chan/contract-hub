"""Pydantic schemas for request/response validation."""

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field, field_validator


# ── Auth ──────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Users ─────────────────────────────────────────────

class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=100)
    role: str = Field(default="user")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ("admin", "user"):
            raise ValueError("role must be 'admin' or 'user'")
        return v


class UserUpdate(BaseModel):
    username: Optional[str] = Field(None, min_length=1, max_length=50)
    password: Optional[str] = Field(None, min_length=6, max_length=100)
    role: Optional[str] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("admin", "user"):
            raise ValueError("role must be 'admin' or 'user'")
        return v


# ── Contracts ─────────────────────────────────────────

class ContractCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="")


class ContractUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None


class ContractResponse(BaseModel):
    id: int
    title: str
    description: str
    status: str
    creator_id: int
    created_at: datetime
    updated_at: datetime
    creator: Optional[UserResponse] = None
    attachments: List["AttachmentResponse"] = []

    model_config = {"from_attributes": True}


# ── Attachments ───────────────────────────────────────

class AttachmentResponse(BaseModel):
    id: int
    filename: str
    original_name: str
    file_size: int
    content_type: str
    contract_id: int
    uploader_id: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Generic Messages ──────────────────────────────────

class MessageResponse(BaseModel):
    message: str


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    page_size: int
