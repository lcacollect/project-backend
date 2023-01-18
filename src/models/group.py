from typing import Optional

from lcacollect_config.formatting import string_uuid
from sqlmodel import Field, Relationship, SQLModel


class MemberGroupLink(SQLModel, table=True):
    member_id: Optional[str] = Field(default=None, foreign_key="projectmember.id", primary_key=True, nullable=False)
    group_id: Optional[str] = Field(default=None, foreign_key="projectgroup.id", primary_key=True, nullable=False)


class ProjectGroup(SQLModel, table=True):
    """ProjectGroup database class"""

    id: Optional[str] = Field(
        default_factory=string_uuid,
        primary_key=True,
        index=True,
        nullable=False,
        sa_column_kwargs={"unique": True},
    )
    name: str = Field(index=True)

    lead_id: Optional[str] = Field(foreign_key="projectmember.id", nullable=True)
    lead: "ProjectMember" = Relationship(back_populates="leader_of")  # one-many

    members: list["ProjectMember"] = Relationship(
        back_populates="project_groups", link_model=MemberGroupLink
    )  # many-many

    project_id: Optional[str] = Field(default=None, foreign_key="project.id", nullable=False)
    project: "Project" = Relationship(back_populates="groups")
