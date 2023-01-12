import pytest
from httpx import AsyncClient
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from models.group import ProjectGroup


@pytest.mark.asyncio
async def test_get_project_groups(client: AsyncClient, project_with_groups, mock_members_from_azure):

    query = """
    query($projectId: String!) {
        projectGroups(projectId: $projectId) {
            id
            name
            leadId
            projectId
            lead {
                userId
            }
            members {
                userId
            }
        }
    }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"projectId": project_with_groups.id}},
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")

    assert isinstance(data["data"]["projectGroups"], list)
    assert all(group["projectId"] == project_with_groups.id for group in data["data"]["projectGroups"])
    assert set(data["data"]["projectGroups"][0].keys()) == {
        "id",
        "leadId",
        "name",
        "projectId",
        "lead",
        "members",
    }


@pytest.mark.asyncio
async def test_get_project_groups_filters(client: AsyncClient, project_with_groups, mock_members_from_azure):

    query = """
    query($projectId: String!, $name: String!) {
        projectGroups(projectId: $projectId, filters: {name: {equal: $name}}) {
            id
            name
            leadId
            projectId
            lead {
                userId
            }
            members {
                userId
            }
        }
    }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {"projectId": project_with_groups.id, "name": "Group 0"},
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert set(data["data"]["projectGroups"][0].keys()) == {
        "id",
        "leadId",
        "name",
        "projectId",
        "lead",
        "members",
    }


@pytest.mark.asyncio
async def test_add_project_group_mutation(client: AsyncClient, projects, project_members, mocker):
    mocker.patch("schema.group.project_exists", return_value=True)
    query = """
    mutation($projectId: String!, $name: String!){
        addProjectGroup(projectId: $projectId, name: $name){
            projectId
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
                "name": "New Group",
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert not data.get("errors")

    assert data["data"]["addProjectGroup"] == {
        "projectId": projects[0].id,
        "name": "New Group",
    }


@pytest.mark.asyncio
async def test_update_project_group_mutation(client: AsyncClient, project_groups):
    query = """
    mutation($id: String!, $name: String, $leadId: String){
        updateProjectGroup(id: $id, name: $name, leadId: $leadId){
            id
            name
            projectId
            leadId
        }
    }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "id": project_groups[0].id,
                "name": "New Group Name",
                "leadId": project_groups[1].lead_id,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert data["data"]["updateProjectGroup"] == {
        "id": project_groups[0].id,
        "name": "New Group Name",
        "projectId": project_groups[0].project_id,
        "leadId": project_groups[1].lead_id,
    }


@pytest.mark.asyncio
async def test_delete_project_group_mutation(client: AsyncClient, db, project_groups):

    query = f"""
        mutation {{
            deleteProjectGroup(id: "{project_groups[0].id}")
        }}
    """

    response = await client.post(f"{settings.API_STR}/graphql", json={"query": query, "variables": None})

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")

    async with AsyncSession(db) as session:
        query = select(ProjectGroup)
        _groups = await session.exec(query)
        _groups = _groups.all()

    assert len(_groups) == len(project_groups) - 1
