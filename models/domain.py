"""Domain models for core business entities."""
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from datetime import datetime
from uuid import UUID


class Message(BaseModel):
    """Message entity."""
    
    id: Optional[int] = Field(default=None, description="Message ID (auto-generated)")
    session_id: str = Field(..., description="Session UUID this message belongs to")
    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Role of the message sender"
    )
    content: str = Field(..., min_length=1, description="Message content")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Message creation timestamp"
    )
    
    @validator('content')
    def content_not_empty(cls, v):
        """Ensure content is not just whitespace."""
        if not v or not v.strip():
            raise ValueError('Message content cannot be empty')
        return v
    
    @validator('session_id')
    def validate_session_id(cls, v):
        """Validate session_id is valid UUID format."""
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError('session_id must be a valid UUID format')
        return v
    
    class Config:
        """Pydantic config."""
        orm_mode = True  # Allow creation from ORM objects
        schema_extra = {
            "example": {
                "id": 1,
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "role": "user",
                "content": "¿Cuáles son las tasas de interés actuales?",
                "timestamp": "2026-02-10T10:30:00Z"
            }
        }


class Session(BaseModel):
    """Session entity."""
    
    session_id: str = Field(..., description="Unique session UUID")
    name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional session name"
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Session creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last activity timestamp"
    )
    message_count: Optional[int] = Field(
        default=0,
        ge=0,
        description="Number of messages in session"
    )
    
    @validator('session_id')
    def validate_session_id(cls, v):
        """Validate session_id is valid UUID format."""
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError('session_id must be a valid UUID format')
        return v
    
    @validator('name')
    def name_not_empty(cls, v):
        """Ensure name is not just whitespace if provided."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v
    
    class Config:
        """Pydantic config."""
        orm_mode = True  # Allow creation from ORM objects
        schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "name": "Consulta financiera - Enero 2026",
                "created_at": "2026-02-10T10:00:00Z",
                "updated_at": "2026-02-10T10:30:00Z",
                "message_count": 5
            }
        }


class DocumentMetadata(BaseModel):
    """Metadata for uploaded documents."""
    
    file_id: str = Field(..., description="Unique file identifier")
    session_id: str = Field(..., description="Session UUID this file belongs to")
    original_filename: str = Field(..., description="Original uploaded filename")
    stored_path: str = Field(..., description="Server storage path")
    file_size: Optional[int] = Field(default=None, ge=0, description="File size in bytes")
    mime_type: Optional[str] = Field(default=None, description="MIME type")
    uploaded_at: Optional[datetime] = Field(
        default=None,
        description="Upload timestamp"
    )
    
    @validator('session_id')
    def validate_session_id(cls, v):
        """Validate session_id is valid UUID format."""
        try:
            UUID(v)
        except (ValueError, AttributeError):
            raise ValueError('session_id must be a valid UUID format')
        return v
    
    class Config:
        """Pydantic config."""
        orm_mode = True
        schema_extra = {
            "example": {
                "file_id": "abc123def456",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "original_filename": "documento.pdf",
                "stored_path": "/uploads/550e8400.../abc123def456.pdf",
                "file_size": 1024000,
                "mime_type": "application/pdf",
                "uploaded_at": "2026-02-10T10:30:00Z"
            }
        }
