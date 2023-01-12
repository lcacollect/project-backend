import strawberry
from lcaconfig.context import get_session
from lcaconfig.exceptions import DatabaseItemNotFound
from sqlalchemy.orm import selectinload
from sqlmodel import select
from strawberry.types import Info

import models.project as models_project
import models.stage as models_stage
from core.validate import project_exists


@strawberry.type
class GraphQLLifeCycleStage:
    id: str
    name: str
    category: str
    phase: str


@strawberry.type
class GraphQLProjectStage:
    stage_id: str
    project_id: str

    @strawberry.field
    def name(self) -> str:
        return self.stage.name

    @strawberry.field
    def category(self) -> str:
        return self.stage.category

    @strawberry.field
    def phase(self) -> str:
        return self.stage.phase


async def get_life_cycle_stages_query(info: Info) -> list[GraphQLLifeCycleStage]:

    """Get all life cycle stages"""

    session = info.context.get("session")
    query = select(models_stage.LifeCycleStage)
    stages = await session.exec(query)

    return stages.all()


async def get_project_stages_query(info: Info, project_id: str) -> list[GraphQLProjectStage]:

    """Get all life cycle stage associated with a project"""

    session = get_session(info)
    await project_exists(session, project_id)

    query = (
        select(models_stage.ProjectStage)
        .where(models_stage.ProjectStage.project_id == project_id)
        .options(selectinload(models_stage.ProjectStage.stage))
    )
    stages = await session.exec(query)

    return stages.all()


async def add_project_stage_mutation(info: Info, project_id: str, stage_id: str) -> GraphQLProjectStage:

    """Add a life cycle stage to a project"""

    session = info.context.get("session")
    if not await project_exists(project_id=project_id, session=session):
        raise DatabaseItemNotFound(f"Project with id: {project_id} does not exist")

    project = await session.get(models_project.Project, project_id)
    life_cycle_stage = await session.get(models_stage.LifeCycleStage, stage_id)
    project_stage = models_stage.ProjectStage(stage=life_cycle_stage, project=project)
    session.add(project_stage)
    await session.commit()

    query = (
        select(models_stage.ProjectStage)
        .where(
            models_stage.ProjectStage.stage == life_cycle_stage,
            models_stage.ProjectStage.project == project,
        )
        .options(selectinload(models_stage.ProjectStage.stage))
    )
    await session.exec(query)

    return project_stage


async def delete_project_stage_mutation(info: Info, project_id: str, stage_id: str) -> str:

    """Remove a life cycle stage from a project"""

    session = info.context.get("session")
    if not await project_exists(project_id=project_id, session=session):
        raise DatabaseItemNotFound(f"Project with id: {project_id} does not exist")

    query = select(models_stage.ProjectStage).where(
        models_stage.ProjectStage.stage_id == stage_id,
        models_stage.ProjectStage.project_id == project_id,
    )
    stage = (await session.exec(query)).one()

    await session.delete(stage)
    await session.commit()

    return stage_id
