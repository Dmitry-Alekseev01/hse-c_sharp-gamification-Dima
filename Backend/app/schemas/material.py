from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List

class MaterialCreate(BaseModel):
    title: str
    description: str | None = None
    content_text: str
    content_url: str | None = None
    video_url: str | None = None
    required_level_id: int | None = None
    related_test_ids: List[int] | None = None


class MaterialUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    content_text: str | None = None
    content_url: str | None = None
    video_url: str | None = None
    required_level_id: int | None = None
    related_test_ids: List[int] | None = None


class MaterialRead(BaseModel):
    id: int
    title: str
    description: str | None
    content_text: str
    content_url: str | None
    video_url: str | None
    published_at: datetime | None
    author_id: int | None
    required_level_id: int | None
    related_test_ids: List[int]

    model_config = ConfigDict(from_attributes=True)
