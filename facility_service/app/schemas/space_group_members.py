# app/schemas/space_group_members.py
from pydantic import BaseModel

class SpaceGroupMemberBase(BaseModel):
    group_id: str
    space_id: str

class SpaceGroupMemberCreate(SpaceGroupMemberBase):
    pass

class SpaceGroupMemberOut(SpaceGroupMemberBase):
    model_config = {
    "from_attributes": True
}
