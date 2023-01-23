import asyncio
import json

import pytest
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from models.group import ProjectGroup
from models.member import ProjectMember
from models.project import Project
from models.stage import LifeCycleStage, ProjectStage


@pytest.fixture
def non_mocked_hosts() -> list:
    return [f"test.com"]


@pytest.fixture
async def projects(db) -> list[Project]:
    projects = []
    async with AsyncSession(db) as session:
        for i in range(3):
            project = Project(
                name=f"Project {i}",
                project_id="some_id",
                meta_fields={},
                groups=[],
                members=[ProjectMember(user_id="someid0")],
                stages=[],
            )
            session.add(project)
            projects.append(project)
        await session.commit()
        [await session.refresh(project) for project in projects]
        query = select(Project).options(selectinload(Project.members))
        projects = (await session.exec(query)).all()

    yield projects


@pytest.fixture
async def life_cycle_stages(db, datafix_dir) -> list[LifeCycleStage]:
    stages = []
    stage_data = json.loads((datafix_dir / "life_cycle_stages.json").read_text())

    async with AsyncSession(db) as session:
        for data in stage_data:
            stage = LifeCycleStage(**data)
            session.add(stage)
            stages.append(stage)
        await session.commit()
        [await session.refresh(stage) for stage in stages]

    yield stages


@pytest.fixture
async def project_with_stages(db, life_cycle_stages, projects) -> Project:
    project = projects[0]

    async with AsyncSession(db) as session:
        for stage in life_cycle_stages:
            project_stage = ProjectStage(stage=stage, project=project)
            session.add(project_stage)
        await session.commit()
        await session.refresh(project)
        [await session.refresh(stage) for stage in life_cycle_stages]

    yield project


@pytest.fixture
async def project_members(db, datafix_dir, projects) -> list[ProjectMember]:
    project_members = []
    project_member_data = json.loads((datafix_dir / "project_members.json").read_text())

    async with AsyncSession(db) as session:
        for index, data in enumerate(project_member_data):
            project_member = ProjectMember(user_id=f"someid{index}", project=projects[0], name=f"name{index}")
            session.add(project_member)
            project_members.append(project_member)

        await session.commit()
        await session.refresh(projects[0])
        [await session.refresh(project_member) for project_member in project_members]

    yield project_members


@pytest.fixture
async def project_with_members(db, datafix_dir, projects) -> Project:
    project = projects[0]
    project_member_data = json.loads((datafix_dir / "project_members.json").read_text())

    async with AsyncSession(db) as session:
        for index, data in enumerate(project_member_data):
            project_member = ProjectMember(
                project_group=data.get("project_group"),
                user_id=f"someid{index}",
                project_id=project.id,
            )
            session.add(project_member)

        await session.commit()
    yield project


@pytest.fixture
async def users_from_azure(datafix_dir) -> list[dict[str, str]]:
    users = json.loads((datafix_dir / "project_members.json").read_text())

    for user in users:
        user.pop("project_group")
        user.pop("role")

    yield users


@pytest.fixture
async def project_with_groups(db, projects, project_members) -> Project:
    project = projects[0]

    groups = []
    async with AsyncSession(db) as session:
        for i in range(3):
            group = ProjectGroup(
                name=f"Group {i}",
                lead_id=project_members[i].id,
                members=project_members,
                project=project,
            )
            groups.append(group)
            session.add(group)

        await session.commit()
        await session.refresh(project)
        [await session.refresh(group) for group in groups]
        query = select(Project).options(selectinload(Project.groups)).options(selectinload(Project.members))
        project = (await session.exec(query)).first()

    yield project


@pytest.fixture
async def project_groups(db, projects, project_members) -> list[ProjectGroup]:
    project = projects[0]
    groups = []
    async with AsyncSession(db) as session:
        for i in range(3):
            group = ProjectGroup(
                name=f"Group {i}",
                members=[ProjectMember(name="Jack", user_id="someid0")],
                lead_id=project_members[i].id,
                project=project,
            )
            groups.append(group)
            session.add(group)
        await session.commit()
        [await session.refresh(group) for group in groups]

    yield groups


@pytest.fixture
async def group_with_members(db, projects, project_members) -> ProjectGroup:
    project = projects[0]
    async with AsyncSession(db) as session:
        group = ProjectGroup(
            name=f"Group One",
            project_id=project.id,
            lead_id=project_members[0].id,
            # project=project,
            members=project_members,
        )
        session.add(group)
        await session.commit()
        [await session.refresh(member) for member in project_members]
        await session.refresh(group)

    yield group


@pytest.fixture
async def base64_encoded_image():
    return """
    iVBORw0KGgoAAAANSUhEUgAAAB0AAAAbCAYAAACAyoQSAAAAAXNSR0IArs4c6QAAAARnQU1BAACx
    jwv8YQUAAAAJcEhZcwAADsMAAA7DAcdvqGQAAAKaSURBVEhL7ZY9TFNRFMd/z36BpYi0IKUxpURM
    J7ALGiwJCU4kJBCHboxMbE5MxImJTmxubAyKiYmJiS7SGNuYkDA1wRRrpOWjra+8hn5R8b36kFDo
    a4vCxC95eeece9J/z7n33Fbo67t/xBVzQ32Xsdls6PV61bs8ToleFdei2gjtzLY68Qmq3yAXEG1h
    sWccX88Isy4Pk2q0ERoWdRuduJpUx9SB16hTnfqpKeoQmvEqbZRbOm8fZ6FVh1RMsf5tg0QuQ6F1
    lPd2959Wy7mjdbT81OWgzKkoihweHpZ9x80RXt1zYipmSWSivI0HCZnHmDd8ZjiRYso2gS//juls
    J3PdHgbMtzAZCmxGXjKZKZQ/4zw0K/U2WzEphqFEZCeI/1cvzzoPWEmmyutLyTWkrof4SlGmE6Is
    qESN2EzNilEVTdHl1EcCklxlLMiS/MVnOjwQ/4T/uDdHUfxxI2PWdjiQc2Jp8lKYFTGtJpyP9p4e
    7RGSRCL7PwjoPUw0RViqaFsoEyRsfsSCLot/P05M2sBfUherUOfpNTJ3p5fYzhorauSENPM7IgPy
    +qAaqUV9ouYhnrDOYk71K9jKfWFV8DCjvZV/0RYV7HgtbQzaLYS2Nwip4bMUeC6vW++66bY4maox
    Npoj47M+ZdbRIlslpJ9xElp7pWvDdVvJBWnrNcPJ6odJs9LNvEheMYry4REyrO5+YDJ29pnZ/cqe
    UCJfVJILJPJZxaiKZqUKyo3kIksA+Ubqekx/Ud7bpMQDi4WIlMRhHWLM8J0X22GW5QPnlUUDNf6L
    1BStxG30sNjXj6185aYJhd8wXagxIxXUOTInhAsRwsfdy+0SalBQoeFKyyi/p+X2Rlmu0crzuJjo
    P9Jwe/8H16KXCPwGYs0ECvdAZ4QAAAAASUVORK5CYII=
    """.strip()


@pytest.fixture
async def mock_members_from_azure(users_from_azure, mocker):
    mocker.patch("schema.member.get_users_from_azure", return_value=users_from_azure)
    yield users_from_azure


@pytest.fixture
def blob_client_mock(mocker):

    class FakeBlob:
        async def upload_blob(self, data):
            return asyncio.Future()

    mocker.patch("azure.storage.blob.aio.BlobClient.__init__", return_value=None)
    mocker.patch("azure.storage.blob.aio.BlobClient.__aenter__", return_value=FakeBlob())
    mocker.patch("azure.storage.blob.aio.BlobClient.__aexit__", return_value=None)
