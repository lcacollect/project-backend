import pytest
from httpx import AsyncClient
from requests import Response
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from models.member import ProjectMember


@pytest.mark.asyncio
async def test_get_project_members(client: AsyncClient, mock_members_from_azure, project_with_members, mocker):
    mocker.patch("core.validate.project_exists", return_value=True)
    query = """
        query($projectId: String!) {
            projectMembers(projectId: $projectId) {
                email
                name
                company
                lastLogin
                leaderOf{
                    name
                }
                projectGroups{
                    name
                }
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"projectId": project_with_members.id}},
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert len(data["data"]["projectMembers"]) == 4
    assert set(data["data"]["projectMembers"][0].keys()) == {
        "email",
        "name",
        "company",
        "lastLogin",
        "leaderOf",
        "projectGroups",
    }


@pytest.mark.asyncio
async def test_get_project_member_for_id(client: AsyncClient, project_with_members, mock_members_from_azure):
    query = """
        query($projectId: String!) {
            projectMembers(projectId: $projectId) {
                email
                name
                company
                lastLogin
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"projectId": project_with_members.id}},
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert len(data["data"]["projectMembers"]) == 4
    assert set(data["data"]["projectMembers"][0].keys()) == {
        "email",
        "name",
        "company",
        "lastLogin",
    }


@pytest.mark.asyncio
async def test_get_project_member_bad_id(
    client: AsyncClient,
    project_with_members,
    mock_members_from_azure,
    mocker,
):
    mocker.patch("core.validate.project_exists", return_value=False)
    query = """
        query($projectId: String!) {
            projectMembers(projectId: $projectId) {
                email
                name
                company
                lastLogin
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"projectId": "badId"}},
    )

    assert response.status_code == 200
    data = response.json()

    assert data.get("errors")


@pytest.mark.asyncio
async def test_add_project_member(client: AsyncClient, project_groups, mocker):
    mocker.patch("schema.member.project_exists", return_value=True)
    mocker.patch("schema.member.get_aad_user_by_email", return_value={"id": "123"})
    mocker.patch("schema.member.invite_user_to_aad", return_value=Response())
    mocker.patch("schema.member.send_email")
    mocker.patch(
        "schema.member.get_users_from_azure",
        return_value=[
            {
                "name": "Test Name",
                "email": "test@test.com",
                "company": "Arkitema",
                "last_login": None,
                "user_id": "123",
            }
        ],
    )
    query = """
        mutation($name: String!, $email: String!, $projectId: String!, $projectGroupIds:[String!]!) {
            addProjectMember(name: $name, email: $email, projectId: $projectId, projectGroupIds: $projectGroupIds) {
                email
                name
                company
                lastLogin
                projectGroups{
                    name
                }
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "projectId": project_groups[0].project_id,
                "name": "Test Name",
                "email": "test@test.com",
                "projectGroupIds": [group.id for group in project_groups][:2],
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert not data.get("errors")
    assert data["data"]["addProjectMember"] == {
        "name": "Test Name",
        "email": "test@test.com",
        "company": "Arkitema",
        "lastLogin": None,
        "projectGroups": [{"name": "Group 0"}, {"name": "Group 1"}],
    }


@pytest.mark.asyncio
async def test_delete_project_member(client: AsyncClient, project_members, db):
    query = """
        mutation($id: String!) {
            deleteProjectMember(id: $id)
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={"query": query, "variables": {"id": project_members[0].id}},
    )

    assert response.status_code == 200
    data = response.json()

    assert not data.get("errors")
    assert data["data"]["deleteProjectMember"] == project_members[0].id
    async with AsyncSession(db) as session:
        query = select(ProjectMember)
        _projectMembers = await session.exec(query)
        _projectMembers = _projectMembers.all()

    for member in _projectMembers:
        assert member.id != project_members[0].id


@pytest.mark.asyncio
async def test_add_project_members_to_group(
    client: AsyncClient, group_with_members, project_members, mock_members_from_azure
):
    member_ids = [member.id for member in project_members][2]

    query = """
        mutation($groupId: String!, $memberIds: [String!]!){
            addProjectMembersToGroup(groupId: $groupId, memberIds: $memberIds){
                id
                name
                lead{
                    id
                }
                members{
                    id
                }
                leadId
                projectId
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "groupId": group_with_members.id,
                "memberIds": member_ids,
            },
        },
    )
    assert response.status_code == 200

    data = response.json()
    print(data)
    assert not data.get("errors")
    assert data["data"]["addProjectMembersToGroup"]["lead"]["id"]
    assert data["data"]["addProjectMembersToGroup"]["members"][0]["id"]


@pytest.mark.asyncio
async def test_remove_project_members_from_group(
    client: AsyncClient, group_with_members, project_members, mock_members_from_azure
):
    member_ids_to_remove = [member.id for member in project_members][2]

    assert member_ids_to_remove
    query = """
        mutation($groupId: String!, $memberIds: [String!]!){
            removeProjectMembersFromGroup(groupId: $groupId, memberIds: $memberIds){
                id
                name
                leadId
                lead{
                    id
                }
                members{
                    id
                }
                projectId
            }
        }
    """

    response = await client.post(
        f"{settings.API_STR}/graphql",
        json={
            "query": query,
            "variables": {
                "groupId": group_with_members.id,
                "memberIds": member_ids_to_remove,
            },
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert not data.get("errors")
    assert len(data["data"]["removeProjectMembersFromGroup"]["members"]) == 2
