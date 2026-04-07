from datetime import datetime
from enum import Enum
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class MaterialType(str, Enum):
    LESSON = "lesson"
    MODULE = "module"
    ARTICLE = "article"


class MaterialStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class MaterialBlockType(str, Enum):
    TEXT = "text"
    DOCUMENTATION_LINK = "documentation_link"
    VIDEO_LINK = "video_link"
    CODE_EXAMPLE = "code_example"


class AttachmentKind(str, Enum):
    PDF = "pdf"
    DOCX = "docx"
    PPTX = "pptx"
    OTHER = "other"


class MaterialBlockCreate(BaseModel):
    block_type: MaterialBlockType
    title: str | None = None
    body: str | None = None
    url: str | None = None
    order_index: int = 0


class MaterialBlockRead(BaseModel):
    id: int
    block_type: MaterialBlockType
    title: str | None
    body: str | None
    url: str | None
    order_index: int

    model_config = ConfigDict(from_attributes=True)


class MaterialAttachmentCreate(BaseModel):
    title: str
    file_url: str
    file_kind: AttachmentKind = AttachmentKind.OTHER
    order_index: int = 0
    is_downloadable: bool = True


class MaterialAttachmentRead(BaseModel):
    id: int
    title: str
    file_url: str
    file_kind: AttachmentKind
    order_index: int
    is_downloadable: bool

    model_config = ConfigDict(from_attributes=True)


class MaterialCreate(BaseModel):
    title: str
    material_type: MaterialType = MaterialType.LESSON
    status: MaterialStatus = MaterialStatus.PUBLISHED
    description: str | None = None
    required_level_id: int | None = None
    related_test_ids: List[int] | None = None
    blocks: list[MaterialBlockCreate] = Field(default_factory=list)
    attachments: list[MaterialAttachmentCreate] = Field(default_factory=list)


class MaterialUpdate(BaseModel):
    title: str | None = None
    material_type: MaterialType | None = None
    status: MaterialStatus | None = None
    description: str | None = None
    required_level_id: int | None = None
    related_test_ids: List[int] | None = None
    blocks: list[MaterialBlockCreate] | None = None
    attachments: list[MaterialAttachmentCreate] | None = None


class MaterialRead(BaseModel):
    id: int
    title: str
    material_type: MaterialType
    status: MaterialStatus
    description: str | None
    published_at: datetime | None
    author_id: int | None
    required_level_id: int | None
    related_test_ids: List[int]
    blocks: list[MaterialBlockRead]
    attachments: list[MaterialAttachmentRead]

    model_config = ConfigDict(from_attributes=True)
