from pydantic import BaseModel

from app.schemas.question import QuestionRead
from app.schemas.test_ import TestRead


class TestContentRead(BaseModel):
    test: TestRead
    questions: list[QuestionRead]
