import pytest
from httpx import AsyncClient
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from models.project import Project


@pytest.mark.asyncio
async def test_get_life_cycle_stages(client: AsyncClient, life_cycle_stages):
    query = """
        query {
            lifeCycleStages {
                name
                id
                category
                phase
            }
        }
    """

    response = await client.post(f"{settings.API_STR}/graphql", json={"query": query, "variables": None})

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert isinstance(data["data"]["lifeCycleStages"], list)
    assert set(data["data"]["lifeCycleStages"][0].keys()) == {
        "name",
        "id",
        "category",
        "phase",
    }


@pytest.mark.asyncio
async def test_get_project_stages(client: AsyncClient, project_with_stages, life_cycle_stages, mocker):
    mocker.patch("schema.stage.project_exists", return_value=True)
    query = """
        query($projectId: String!) {
            projectStages(projectId: $projectId) {
                name
                category
                phase
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"projectId": project_with_stages.id}},
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert isinstance(data["data"]["projectStages"], list)
    assert len(data["data"]["projectStages"]) == len(life_cycle_stages)
    assert set(data["data"]["projectStages"][0].keys()) == {"name", "category", "phase"}


@pytest.mark.asyncio
async def test_add_project_stage(client: AsyncClient, projects, life_cycle_stages, mocker):
    mocker.patch("schema.stage.project_exists", return_value=True)
    query = """
        mutation($projectId: String!, $stageId: String!) {
            addProjectStage(projectId: $projectId, stageId: $stageId) {
                name
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "projectId": projects[0].id,
                "stageId": life_cycle_stages[0].id,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert data["data"]["addProjectStage"] == {
        "name": life_cycle_stages[0].name,
    }


@pytest.mark.asyncio
async def test_delete_project_stage(db, client: AsyncClient, project_with_stages, life_cycle_stages, mocker):
    mocker.patch("schema.stage.project_exists", return_value=True)
    query = """
        mutation($projectId: String!, $stageId: String!) {
            deleteProjectStage(projectId: $projectId, stageId: $stageId)
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "projectId": project_with_stages.id,
                "stageId": life_cycle_stages[0].id,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")

    async with AsyncSession(db) as session:
        query = select(Project).where(Project.id == project_with_stages.id).options(selectinload(Project.stages))
        _project = await session.exec(query)
        _project = _project.one()

    assert len(_project.stages) == len(life_cycle_stages) - 1
