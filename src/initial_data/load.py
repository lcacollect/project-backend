import asyncio
import json
from pathlib import Path

from lcaconfig.connection import create_postgres_engine
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from models.group import ProjectGroup
from models.member import ProjectMember
from models.project import Project
from models.stage import LifeCycleStage, ProjectStage


async def load_project(path: Path):
    data = json.loads(path.read_text())
    async with AsyncSession(create_postgres_engine()) as session:
        project = await session.get(Project, data.get("id"))
        if not project:
            project = Project(**data)
            session.add(project)
            await session.commit()
            await session.refresh(project)

    return project


async def load_members(path: Path):
    data = json.loads(path.read_text())
    members = []
    async with AsyncSession(create_postgres_engine()) as session:
        for member_data in data:
            member = await session.get(ProjectMember, member_data.get("id"))
            if not member:
                member = ProjectMember(**member_data)
                session.add(member)
                await session.commit()
                await session.refresh(member)
            members.append(member)
    return members


async def load_groups(path: Path):
    data = json.loads(path.read_text())
    groups = []
    async with AsyncSession(create_postgres_engine()) as session:
        for group_data in data:
            group = await session.get(ProjectGroup, group_data.get("id"))
            if not group:
                group = ProjectGroup(**group_data)
                session.add(group)
                await session.commit()
                await session.refresh(group)
            groups.append(group)

    return groups


async def load_stages(path: Path):
    data = json.loads(path.read_text())
    stages = []
    async with AsyncSession(create_postgres_engine()) as session:
        for stage_data in data:
            stage = (
                await session.exec(select(ProjectStage).where(ProjectStage.project_id == stage_data.get("id")))
            ).first()
            if not stage:
                life_cycle_stage = (
                    await session.exec(select(LifeCycleStage).where(LifeCycleStage.phase == "A1-A3"))
                ).first()
                stage = ProjectStage(**stage_data, stage_id=life_cycle_stage.id)
                session.add(stage)
                await session.commit()
                await session.refresh(stage)
            stages.append(stage)

    return stages


async def load_project_data(path: Path):
    await load_project(path / "project.json")
    await load_members(path / "members.json")
    await load_groups(path / "groups.json")
    await load_stages(path / "stages.json")


if __name__ == "__main__":
    p = Path(__file__).parent

    asyncio.run(load_project_data(p))
