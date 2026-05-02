from pydantic import BaseModel, Field

from app.schemas.question import ChoiceCreate, QuestionRead
from app.schemas.test_ import TestRead


class TestContentRead(BaseModel):
    test: TestRead
    questions: list[QuestionRead]


class TestQuestionDraftWrite(BaseModel):
    text: str
    points: float = Field(default=1.0, ge=0)
    is_open_answer: bool = False
    material_urls: list[str] | None = None
    choices: list[ChoiceCreate] = Field(default_factory=list)


class TestContentWrite(BaseModel):
    questions: list[TestQuestionDraftWrite] = Field(default_factory=list)
