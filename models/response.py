"""Response models for API endpoints."""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime


class ErrorResponse(BaseModel):
    """Standard error response."""
    
    ok: Literal[False] = False
    error: str = Field(..., description="Error message")
    code: Optional[str] = Field(
        default=None,
        description="Error code for programmatic handling"
    )
    rejected: Optional[bool] = Field(
        default=None,
        description="True if request was rejected by guardrail"
    )
    reason: Optional[str] = Field(
        default=None,
        description="Rejection reason from guardrail"
    )
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "ok": False,
                "error": "Invalid request",
                "code": "VALIDATION_ERROR"
            }
        }


class QueryResponse(BaseModel):
    """Response model for /api/query endpoint."""
    
    ok: Literal[True] = True
    reply: str = Field(..., description="Agent response text")
    session_id: str = Field(..., description="Session UUID")
    voice_mode: bool = Field(default=False, description="Voice mode status")
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "ok": True,
                "reply": "Las tasas de interés actuales son...",
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "voice_mode": False
            }
        }


class SessionResponse(BaseModel):
    """Response model for creating a session."""
    
    ok: Literal[True] = True
    session_id: str = Field(..., description="Created session UUID")
    welcome: Optional[str] = Field(
        default=None,
        description="Welcome message for new session"
    )
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "ok": True,
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "welcome": "Bienvenido. Por favor indica si tu consulta será 'financiera' o 'legal'."
            }
        }


class AuthResponse(BaseModel):
    """Response model for auth endpoints."""

    ok: Literal[True] = True
    token: str = Field(..., description="Auth token")
    username: str = Field(..., description="Username")

    class Config:
        schema_extra = {
            "example": {
                "ok": True,
                "token": "abc123token",
                "username": "usuario123"
            }
        }


class SessionInfo(BaseModel):
    """Session information."""
    
    id: str = Field(..., description="Session UUID")
    session_id: Optional[str] = Field(
        default=None,
        description="Session UUID (legacy field)"
    )
    created_at: Optional[str] = Field(
        default=None,
        description="Session creation timestamp"
    )
    message_count: Optional[int] = Field(
        default=None,
        description="Number of messages in session"
    )


class SessionsListResponse(BaseModel):
    """Response model for listing sessions."""
    
    ok: Literal[True] = True
    sessions: List[SessionInfo] = Field(
        default_factory=list,
        description="List of sessions"
    )
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "ok": True,
                "sessions": [
                    {
                        "session_id": "550e8400-e29b-41d4-a716-446655440000",
                        "created_at": "2026-02-10T10:30:00Z",
                        "message_count": 5
                    }
                ]
            }
        }


class MessageInfo(BaseModel):
    """Message information."""
    
    id: int = Field(..., description="Message ID")
    role: Literal["user", "assistant", "system"] = Field(
        ...,
        description="Message role"
    )
    content: str = Field(..., description="Message content")
    timestamp: Optional[str] = Field(
        default=None,
        description="Message timestamp"
    )


class MessagesResponse(BaseModel):
    """Response model for getting session messages."""
    
    ok: Literal[True] = True
    messages: List[MessageInfo] = Field(
        default_factory=list,
        description="List of messages"
    )
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "ok": True,
                "messages": [
                    {
                        "id": 1,
                        "role": "user",
                        "content": "¿Cuáles son las tasas de interés?",
                        "timestamp": "2026-02-10T10:30:00Z"
                    },
                    {
                        "id": 2,
                        "role": "assistant",
                        "content": "Las tasas actuales son...",
                        "timestamp": "2026-02-10T10:30:05Z"
                    }
                ]
            }
        }


class SuccessResponse(BaseModel):
    """Generic success response."""
    
    ok: Literal[True] = True
    message: Optional[str] = Field(
        default=None,
        description="Optional success message"
    )
    
    class Config:
        """Pydantic config."""
        schema_extra = {
            "example": {
                "ok": True,
                "message": "Operation completed successfully"
            }
        }
