# app/schemas/grading.py
from pydantic import BaseModel, ConfigDict, Field

class GradeRequest(BaseModel):
    score: float = Field(..., ge=0)
    comment: str | None = None

class GradeResponse(BaseModel):
    answer_id: int
    score: float

    model_config = ConfigDict(from_attributes=True)
