from pydantic import BaseModel, ConfigDict


class GroupCreate(BaseModel):
    name: str


class GroupRead(BaseModel):
    id: int
    name: str
    teacher_id: int

    model_config = ConfigDict(from_attributes=True)


class GroupMemberRead(BaseModel):
    user_id: int
    username: str
    full_name: str | None = None


class GroupDetailRead(GroupRead):
    members: list[GroupMemberRead]
