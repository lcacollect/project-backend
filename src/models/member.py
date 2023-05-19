from lcacollect_config.formatting import string_uuid
from sqlmodel import Field, Relationship, SQLModel
from typing import Optional

from models.group import MemberGroupLink, ProjectGroup


class ProjectMember(SQLModel, table=True):
    """Project related Member database class"""

    id: Optional[str] = Field(
        default_factory=string_uuid,
        primary_key=True,
        nullable=False,
        sa_column_kwargs={"unique": True},
    )
    project_groups: list[ProjectGroup] = Relationship(back_populates="members", link_model=MemberGroupLink)
    leader_of: Optional[list[ProjectGroup]] = Relationship(back_populates="lead")
    user_id: str
    project_id: Optional[str] = Field(foreign_key="project.id")
    project: "Project" = Relationship(back_populates="members")

    @classmethod
    def create_from_user(
        cls,
        user_id: str,
        project_id: str,
        project_groups: list[ProjectGroup],
    ):
        return cls(
            project_groups=project_groups,
            user_id=user_id,
            project_id=project_id,
        )
