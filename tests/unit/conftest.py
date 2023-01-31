import json
from dataclasses import dataclass

import pytest
from lcacollect_config.connection import create_postgres_engine
from pytest_alembic.config import Config
from sqlmodel.ext.asyncio.session import AsyncSession

from exceptions import MSGraphException
from models.group import ProjectGroup
from models.member import ProjectMember
from models.project import Project


@pytest.fixture
def alembic_config():
    """Override this fixture to configure the exact alembic context setup required."""
    yield Config()


@pytest.fixture
def alembic_engine(postgres):
    """Override this fixture to provide pytest-alembic powered tests with a database handle."""
    yield create_postgres_engine(as_async=False)


@pytest.fixture
async def users(datafix_dir) -> list[dict[str, str]]:
    users = json.loads((datafix_dir / "project_members.json").read_text())

    for user in users:
        user.pop("project_group")
        user.pop("role")

    yield users


@pytest.fixture
async def users_with_groups(datafix_dir) -> list[dict[str, str]]:
    yield json.loads((datafix_dir / "project_members.json").read_text())


@pytest.fixture
async def project(db) -> Project:
    async with AsyncSession(db) as session:
        project = Project(
            name=f"Project",
            project_id="some_id",
            meta_fields={},
            groups=[],
            members=[],
            stages=[],
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)

    yield project


@pytest.fixture
async def project_members(db, users, project) -> list[ProjectMember]:
    project_members = []
    async with AsyncSession(db) as session:
        for data in users:
            project_member = ProjectMember(user_id=data.get("user_id"), project_id=project.id)
            session.add(project_member)
            project_members.append(project_member)

        await session.commit()
        [await session.refresh(project_member) for project_member in project_members]

    yield project_members


@pytest.fixture
async def project_groups(db, users_with_groups, project) -> list[ProjectGroup]:
    project_groups = []
    async with AsyncSession(db) as session:
        for data in users_with_groups:
            project_group = ProjectGroup(name=data.get("project_group"), project_id=project.id)
            session.add(project_group)
            project_groups.append(project_group)

        await session.commit()
        [await session.refresh(project_group) for project_group in project_groups]

    yield project_groups


@pytest.fixture
async def mock_federation_get_users(mocker, users):
    mocker.patch(
        "schema.member.get_users_from_azure",
        return_value=users,
    )
    yield users


@pytest.fixture
async def mock_federation_get_users_none(mocker):
    mocker.patch(
        "schema.member.get_users_from_azure",
        return_value=[],
    )
    yield []


@pytest.fixture
async def mock_federation_get_users_error(mocker):
    mocker.patch("schema.member.get_users_from_azure", return_value=[], side_effect=MSGraphException())
    yield []


@pytest.fixture
def mock_info():
    @dataclass
    class MockInfo:
        context: dict

    return MockInfo
