"""Request models for API validation."""
import re
from pydantic import BaseModel, Field, validator
from typing import Optional, List
from uuid import UUID

USERNAME_RE = re.compile(r"^[A-Za-z0-9]+$")


class QueryRequest(BaseModel):
    """Request model for /api/query endpoint."""
    
    query: str = Field(
        ..., 
        min_length=1, 
        max_length=10000,
        description="User query text"
    )
    voice_mode: bool = Field(
        default=False,
        description="Enable voice mode for response"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session UUID (auto-generated if not provided)"
    )
    
    @validator('query')
    def query_not_empty(cls, v):
        """Ensure query is not just whitespace."""
        if not v or not v.strip():
            raise ValueError('Query cannot be empty or only whitespace')
        return v.strip()
    
    @validator('session_id')
    def validate_session_id(cls, v):
        """Validate session_id is valid UUID format if provided."""
        if v is not None and v.strip():
            try:
                # Try to parse as UUID to validate format
                UUID(v)
            except (ValueError, AttributeError):
                raise ValueError('session_id must be a valid UUID format')
            return v.strip()
        return v
    
    @validator('voice_mode', pre=True)
    def parse_voice_mode(cls, v):
        """Convert various truthy values to boolean."""
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.lower() in ('true', '1', 'yes', 'on')
        return bool(v)
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "query": "¿Cuáles son las tasas de interés actuales?",
                "voice_mode": False,
                "session_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""
    
    name: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Optional session name"
    )
    
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
        schema_extra = {
            "example": {
                "name": "Consulta financiera - Enero 2026"
            }
        }


class RegisterRequest(BaseModel):
    """Request model for user registration."""

    username: str = Field(..., min_length=3, max_length=32, description="Username (alphanumeric)")
    password: str = Field(..., min_length=6, max_length=128, description="User password")
    password_confirm: str = Field(..., min_length=6, max_length=128, description="Password confirmation")

    @validator("username")
    def validate_username(cls, v):
        v = v.strip()
        if not USERNAME_RE.match(v):
            raise ValueError("username must be alphanumeric")
        return v

    class Config:
        schema_extra = {
            "example": {
                "username": "usuario123",
                "password": "secreto123",
                "password_confirm": "secreto123"
            }
        }


class LoginRequest(BaseModel):
    """Request model for user login."""

    username: str = Field(..., min_length=3, max_length=32, description="Username")
    password: str = Field(..., min_length=6, max_length=128, description="User password")

    @validator("username")
    def validate_username(cls, v):
        return v.strip()

    class Config:
        schema_extra = {
            "example": {
                "username": "usuario123",
                "password": "secreto123"
            }
        }
