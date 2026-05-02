"""Shared material taxonomy values used by schemas and admin validation."""

from enum import Enum


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


MATERIAL_BLOCK_TYPE_VALUES: tuple[str, ...] = tuple(item.value for item in MaterialBlockType)
MATERIAL_ATTACHMENT_KIND_VALUES: tuple[str, ...] = tuple(item.value for item in AttachmentKind)
