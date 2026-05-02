from pydantic import BaseModel, ConfigDict

class LevelRead(BaseModel):
    id: int
    name: str
    required_points: int
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class LevelCreate(BaseModel):
    name: str
    required_points: int
    description: str | None = None


class LevelUpdate(BaseModel):
    name: str | None = None
    required_points: int | None = None
    description: str | None = None
