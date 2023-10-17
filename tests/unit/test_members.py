from dataclasses import dataclass

import pytest
from pytest_httpx import HTTPXMock
from sqlmodel.ext.asyncio.session import AsyncSession

from core.config import settings
from core.federation import (
    GraphQLComment,
    GraphQLProjectSource,
    GraphQLTask,
    delete_project_source,
    delete_reporting_schema,
    get_assignee,
    get_author,
    get_comment,
    get_group,
    get_member,
    get_reporting_schema,
    get_source,
    get_task,
)
from models.member import ProjectMember
from schema.group import GraphQLProjectGroup
from schema.member import GraphQLProjectMember


@pytest.mark.skip("For local testing of the MS Graph API")
@pytest.mark.asyncio
async def test_get_user_from_azure():
    from lcacollect_config.user import get_users_from_azure

    users = await get_users_from_azure("f8a9e659-ce95-49cf-b45d-5b0a867a4a17")
    assert users


@pytest.mark.asyncio
async def test_get_member(db, mock_info, mock_federation_get_users, users, project_members):
    async with AsyncSession(db) as session:
        info = mock_info(context={"session": session})
        member, user = await get_member(info, users[0]["user_id"])

    assert member
    assert isinstance(member, ProjectMember)
    assert user
    assert isinstance(user, dict)


@pytest.mark.asyncio
async def test_get_member_no_user(db, mock_info, mock_federation_get_users_none, users, project_members):
    async with AsyncSession(db) as session:
        info = mock_info(context={"session": session})
        member, user = await get_member(info, users[0]["user_id"])

    assert not member
    assert not user


@pytest.mark.asyncio
async def test_get_member_error(db, mock_info, mock_federation_get_users_error, users, project_members):
    async with AsyncSession(db) as session:
        info = mock_info(context={"session": session})
        member, user = await get_member(info, users[0]["user_id"])

    assert not member
    assert not user


@pytest.mark.asyncio
async def test_get_member_no_member(db, mock_info, mock_federation_get_users, users):
    async with AsyncSession(db) as session:
        info = mock_info(context={"session": session})
        member, user = await get_member(info, users[0]["user_id"])

    assert not member
    assert user
    assert isinstance(user, dict)


@pytest.mark.asyncio
async def test_get_assignee(db, mock_info, mock_federation_get_users, users, project_members, project_groups):
    task = GraphQLTask(
        id="taskid",
        author_id=users[0]["user_id"],
        assignee_id=users[1]["user_id"],
        assigned_group_id=project_groups[0].id,
        reporting_schema_id="reportingschemaid0",
    )

    async with AsyncSession(db) as session:
        info = mock_info(context={"session": session})
        assignee = await get_assignee(info, task)

    assert assignee
    assert isinstance(assignee, GraphQLProjectMember)


@pytest.mark.asyncio
async def test_get_group_assignee(db, mock_federation_get_users, users, project_members, project_groups):
    task = GraphQLTask(
        id="taskid",
        author_id=users[0]["user_id"],
        assignee_id=None,
        assigned_group_id=project_groups[0].id,
        reporting_schema_id="reportingschemaid0",
    )

    @dataclass
    class Info:
        context: dict

    async with AsyncSession(db) as session:
        info = Info(context={"session": session})
        assignee = await get_assignee(info, task)

    assert assignee.id == project_groups[0].id
    assert isinstance(assignee, GraphQLProjectGroup)


@pytest.mark.asyncio
async def test_get_task_author(db, mock_federation_get_users, users, project_members, project_groups):
    task = GraphQLTask(
        id="taskid",
        author_id=users[0]["user_id"],
        assignee_id=users[1]["user_id"],
        assigned_group_id=project_groups[0].id,
        reporting_schema_id="reportingschemaid0",
    )

    @dataclass
    class Info:
        context: dict

    async with AsyncSession(db) as session:
        info = Info(context={"session": session})
        author = await get_author(info, task)

    assert author
    assert isinstance(author, GraphQLProjectMember)


@pytest.mark.asyncio
async def test_get_source_author(db, mock_federation_get_users, users, project_members, project_groups):
    source = GraphQLProjectSource(
        id="project",
        author_id=users[0]["user_id"],
        project_id="project0",
    )

    @dataclass
    class Info:
        context: dict

    async with AsyncSession(db) as session:
        info = Info(context={"session": session})
        author = await get_author(info, source)

    assert author
    assert isinstance(author, GraphQLProjectMember)


@pytest.mark.asyncio
async def test_get_group(db, users, mock_federation_get_users, project_members, project_groups):
    task = GraphQLTask(
        id="taskid",
        author_id=users[0]["user_id"],
        assignee_id=users[1]["user_id"],
        assigned_group_id=project_groups[0].id,
        reporting_schema_id="reportingschemaid0",
    )

    @dataclass
    class Info:
        context: dict

    async with AsyncSession(db) as session:
        info = Info(context={"session": session})
        group = await get_group(info, task)

    assert group
    assert isinstance(group, GraphQLProjectGroup)


@pytest.mark.asyncio
async def test_get_no_group(db, mock_federation_get_users, users, project_members, project_groups):
    task = GraphQLTask(
        id="taskid",
        author_id=users[0]["user_id"],
        assignee_id=users[1]["user_id"],
        assigned_group_id=None,
        reporting_schema_id="reportingschemaid0",
    )

    @dataclass
    class Info:
        context: dict

    async with AsyncSession(db) as session:
        info = Info(context={"session": session})
        group = await get_group(info, task)

    assert group.id is None and group.name is None
    assert isinstance(group, GraphQLProjectGroup)


@pytest.mark.asyncio
async def test_get_task(httpx_mock: HTTPXMock):
    mock_data = {
        "data": {
            "tasks": [
                {
                    "id": "f8a9e659-ce95-49cf-b45d-5b0a867a4a17",
                    "authorId": "f8a9e659-ce95-49cf-b45d-5b0a867a4a17",
                    "assigneeId": "f8a9e659-ce95-49cf-b45d-5b0a867a4a18",
                    "assignedGroupId": "f8a9e659-ce95-49cf-b45d-5b0a867a4a19",
                    "reportingSchemaId": "f8a9e659-ce95-49cf-b45d-5b0a867a4a20",
                }
            ]
        }
    }
    httpx_mock.add_response(url=f"{settings.ROUTER_URL}/graphql", json=mock_data)
    task = await get_task(
        "3f8a9e659-ce95-49cf-b45d-5b0a867a4a20",
        "f8a9e659-ce95-49cf-b45d-5b0a867a4a17",
        "mytoken",
    )

    assert task
    assert isinstance(task, GraphQLTask)


@pytest.mark.asyncio
async def test_get_source(httpx_mock: HTTPXMock):
    mock_data = {
        "data": {
            "projectSources": [
                {
                    "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
                    "authorId": "1010101-ce95-49cf-b45d-5b0a867a4a17",
                    "projectId": "projectId0",
                }
            ]
        }
    }
    httpx_mock.add_response(url=f"{settings.ROUTER_URL}/graphql", json=mock_data)
    source = await get_source("projectId0", "1010101-ce95-49cf-b45d-5b0a867a4a17", "mytoken")

    assert source
    assert isinstance(source, GraphQLProjectSource)


@pytest.mark.asyncio
async def test_get_comment(httpx_mock: HTTPXMock):
    mock_data = {
        "data": {
            "comments": [
                {
                    "id": "f8a9e659-ce95-49cf-b45d-5b0a867a4a17",
                    "authorId": "f8a9e659-ce95-49cf-b45d-5b0a867a4a17",
                    "taskId": "3f8a9e659-ce95-49cf-b45d-5b0a867a4a20",
                }
            ]
        }
    }
    httpx_mock.add_response(url=f"{settings.ROUTER_URL}/graphql", json=mock_data)
    comment = await get_comment(
        "3f8a9e659-ce95-49cf-b45d-5b0a867a4a20",
        "f8a9e659-ce95-49cf-b45d-5b0a867a4a17",
        "mytoken",
    )

    assert comment
    assert isinstance(comment, GraphQLComment)


@pytest.mark.asyncio
async def test_get_reporting_schema(httpx_mock: HTTPXMock):
    mock_data = {
        "data": {
            "reportingSchemas": [
                {
                    "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
                    "projectId": "projectId0",
                }
            ]
        }
    }
    httpx_mock.add_response(url=f"{settings.ROUTER_URL}/graphql", json=mock_data)
    reporting_schema = await get_reporting_schema("projectId0", "mytoken")

    assert reporting_schema
    assert isinstance(reporting_schema[0], dict)


@pytest.mark.asyncio
async def test_delete_reporting_schema(httpx_mock: HTTPXMock):
    mock_data = {
        "data": {
            "deleteReportingSchema": {
                "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
            }
        }
    }
    httpx_mock.add_response(url=f"{settings.ROUTER_URL}/graphql", json=mock_data)
    id = await delete_reporting_schema(id="1010101-ce95-49cf-b45d-5b0a867a4a17", token="fake-token")
    assert id


@pytest.mark.asyncio
async def test_delete_project_source(httpx_mock: HTTPXMock):
    mock_data = {
        "data": {
            "deleteProjectSource": {
                "id": "1010101-ce95-49cf-b45d-5b0a867a4a17",
            }
        }
    }
    httpx_mock.add_response(url=f"{settings.ROUTER_URL}/graphql", json=mock_data)
    id = await delete_project_source(id="1010101-ce95-49cf-b45d-5b0a867a4a17", token="fake-token")
    assert id
