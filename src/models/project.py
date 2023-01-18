from typing import Optional

from lcacollect_config.formatting import string_uuid
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSON
from sqlmodel import Field, Relationship, SQLModel

from models.group import ProjectGroup
from models.member import ProjectMember
from models.stage import ProjectStage


class Project(SQLModel, table=True):
    """Project database class"""

    id: Optional[str] = Field(default_factory=string_uuid, primary_key=True, nullable=False)
    project_id: str | None
    name: str
    client: str | None
    domain: str | None
    address: str | None
    city: str | None
    country: str | None
    image_url: str | None

    groups: list["ProjectGroup"] = Relationship(back_populates="project")
    stages: list["ProjectStage"] = Relationship(back_populates="project")
    members: list[ProjectMember] = Relationship(back_populates="project")
    meta_fields: dict = Field(default=dict, sa_column=Column(JSON), nullable=False)
