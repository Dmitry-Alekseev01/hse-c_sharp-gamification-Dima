from pydantic import BaseModel, ConfigDict, field_validator
from datetime import datetime

class AnswerCreate(BaseModel):
    user_id: int | None = None
    test_id: int
    attempt_id: int | None = None
    question_id: int
    answer_payload: str

    @field_validator("answer_payload")
    def not_empty(cls, v):
        if v is None or str(v).strip() == "":
            raise ValueError("answer_payload must not be empty")
        return str(v).strip()

    model_config = ConfigDict(from_attributes=True)

class AnswerRead(BaseModel):
    id: int
    user_id: int
    test_id: int
    attempt_id: int | None
    question_id: int
    answer_payload: str
    score: float | None
    graded_by: int | None
    graded_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PendingOpenAnswerRead(BaseModel):
    id: int
    user_id: int
    student_username: str
    test_id: int
    attempt_id: int | None
    question_id: int
    question_text: str
    answer_payload: str
    submitted_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
