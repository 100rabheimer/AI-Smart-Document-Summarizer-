import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DocumentSummary(BaseModel):
    """Structured document summary validated via Pydantic (FR-I1)."""
    title: str = Field(description="Clean, descriptive document title")
    summary: str = Field(description="2-3 sentence executive summary")
    key_points: List[str] = Field(description="Key takeaways or highlights")
    topics: List[str] = Field(description="Categorical topics or tags")


class DocumentBase(BaseModel):
    filename: str
    mime_type: str
    size: int


class DocumentRead(DocumentBase):
    id: uuid.UUID
    user_id: uuid.UUID
    content_hash: str
    status: str
    error: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
