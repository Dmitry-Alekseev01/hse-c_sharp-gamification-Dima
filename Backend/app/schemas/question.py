from pydantic import BaseModel, ConfigDict
from typing import List

class ChoiceCreate(BaseModel):
    question_id: int | None = None
    value: str
    ordinal: int | None = None
    is_correct: bool = False


class ChoiceUpdate(BaseModel):
    value: str | None = None
    ordinal: int | None = None
    is_correct: bool | None = None

class ChoiceRead(BaseModel):
    id: int
    question_id: int
    value: str
    ordinal: int | None

    model_config = ConfigDict(from_attributes=True)


class ChoiceTeacherRead(ChoiceRead):
    is_correct: bool

class QuestionCreate(BaseModel):
    test_id: int
    text: str
    points: float = 1.0
    is_open_answer: bool = False
    material_urls: List[str] | None = None
    choices: List[ChoiceCreate] | None = None


class QuestionUpdate(BaseModel):
    text: str | None = None
    points: float | None = None
    is_open_answer: bool | None = None
    material_urls: List[str] | None = None

class QuestionRead(BaseModel):
    id: int
    test_id: int
    text: str
    points: float
    is_open_answer: bool
    material_urls: List[str] | None = None
    choices: List[ChoiceRead] | None = None

    model_config = ConfigDict(from_attributes=True)


class QuestionTeacherRead(BaseModel):
    id: int
    test_id: int
    text: str
    points: float
    is_open_answer: bool
    material_urls: List[str] | None = None
    choices: List[ChoiceTeacherRead] | None = None

    model_config = ConfigDict(from_attributes=True)
