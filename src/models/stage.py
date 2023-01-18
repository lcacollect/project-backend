from typing import Optional

from lcacollect_config.formatting import string_uuid
from sqlmodel import Field, Relationship, SQLModel


class ProjectStage(SQLModel, table=True):
    stage_id: Optional[str] = Field(default=None, foreign_key="lifecyclestage.id", primary_key=True, nullable=False)
    project_id: Optional[str] = Field(default=None, foreign_key="project.id", primary_key=True, nullable=False)

    project: "Project" = Relationship(back_populates="stages")
    stage: "LifeCycleStage" = Relationship(back_populates="projects")


class LifeCycleStage(SQLModel, table=True):
    """ProjectStage database class"""

    id: Optional[str] = Field(default_factory=string_uuid, primary_key=True, index=True, nullable=False)
    name: str = Field(index=True)
    category: str
    phase: str

    projects: list["ProjectStage"] = Relationship(back_populates="stage")
