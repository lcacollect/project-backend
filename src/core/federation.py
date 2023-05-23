import logging
from typing import TYPE_CHECKING, Annotated, Optional, Union

import httpx
import strawberry
from aiocache import cached
from lcacollect_config.context import get_session, get_token
from lcacollect_config.exceptions import (
    MicroServiceConnectionError,
    MicroServiceResponseError,
)
from sqlalchemy.orm import selectinload
from sqlmodel import select
from strawberry.types import Info

import models.group as models_group
import models.member as models_member
from core.config import settings
from exceptions import MSGraphException

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from schema.group import GraphQLProjectGroup
    from schema.member import GraphQLProjectMember


def cache_key_builder(function, *args, **kwargs):
    return f"{function.__name__}_{args[0]}_{args[1]}"


async def get_author(info: Info, root: "GraphQLTask") -> "GraphQLProjectMember":
    """
    Fetches the author of a Task and
    returns a GraphQLProjectMember class instance
    """
    from schema.member import GraphQLProjectMember

    member, user = await get_member(info, root.author_id)
    if not user:
        logger.info(f"Could not find a user with id: {root.author_id}")
        return GraphQLProjectMember(
            id="",
            project_id="",
            leader_of=[],
            project_groups=[],
            user_id=root.author_id,
            name="User doesn't exist",
            email="",
            company=None,
            last_login=None,
        )
    if not member:
        logger.info(f"Could not find a project member with user_id: {root.author_id}")
        return GraphQLProjectMember(id="", project_id="", leader_of=[], project_groups=[], **user)

    return GraphQLProjectMember(
        id=member.id,
        project_id=member.project_id,
        leader_of=member.leader_of,
        project_groups=member.project_groups,
        **user,
    )


async def get_member(info: Info, member_id: str):
    """Queries a single Project Member from Azure"""
    from lcacollect_config.user import get_users_from_azure

    session = get_session(info)
    try:
        users = await get_users_from_azure(member_id)
        user = users[0]
    except (IndexError, MSGraphException):
        return None, None
    query = (
        select(models_member.ProjectMember)
        .where(models_member.ProjectMember.user_id == member_id)
        .options(selectinload(models_member.ProjectMember.leader_of))
        .options(selectinload(models_member.ProjectMember.project_groups))
    )
    member = (await session.exec(query)).first()
    return member, user


async def get_assignee(info: Info, root: "GraphQLTask") -> Union["GraphQLProjectMember", "GraphQLProjectGroup"]:
    """
    Fetches the assignee of a Task and
    returns a GraphQLProjectMember class instance
    """
    from schema.member import GraphQLProjectMember

    if root.assignee_id:
        member, user = await get_member(info, root.assignee_id)
        if not user:
            logger.info(f"Could not find a user with id: {root.assignee_id}")
            return GraphQLProjectMember(
                id="",
                project_id="",
                leader_of=[],
                project_groups=[],
                user_id=root.assignee_id,
                name="User doesn't exist",
                email="",
                company=None,
                last_login=None,
            )
        if not member:
            logger.info(f"Could not find a project member with user_id: {root.assignee_id}")
            return GraphQLProjectMember(id="", project_id="", leader_of=[], project_groups=[], **user)

        return GraphQLProjectMember(
            id=member.id,
            project_id=member.project_id,
            leader_of=member.leader_of,
            project_groups=member.project_groups,
            **user,
        )
    else:
        return await get_group(info, root)


async def get_group(info: Info, root: "GraphQLTask"):
    """
    Fetches a single Project Group of a Task
    and returns a GraphQLProjectGroup class instance
    """

    from schema.group import GraphQLProjectGroup

    session = get_session(info)

    if not root.assigned_group_id:
        return GraphQLProjectGroup(id=None, lead=None, members=None, name=None, lead_id=None, project_id=None)

    query = (
        select(models_group.ProjectGroup)
        .where(models_group.ProjectGroup.id == root.assigned_group_id)
        .options(selectinload(models_group.ProjectGroup.members))
        .options(selectinload(models_group.ProjectGroup.lead))
    )

    group = (await session.exec(query)).first()

    if not group:
        logger.info(f"Could not find a group with id: {root.assigned_group_id}")
        return GraphQLProjectGroup(
            id=root.assigned_group_id,
            lead=None,
            members=None,
            name="Group doesn't exist",
            lead_id=None,
            project_id=None,
        )

    return GraphQLProjectGroup(
        id=group.id,
        lead=group.lead,
        lead_id=group.lead_id,
        members=group.members,
        name=group.name,
        project_id=group.project_id,
    )


@cached(ttl=60, key_builder=cache_key_builder)
async def get_task(reporting_schema_id: str, id: str, token: str) -> "GraphQLTask":
    """
    Queries a task from the Documentation Module and
    returns a GraphQLTask class instance
    """

    query = """
          query ($reportingSchemaId: String!, $id: String!){
              tasks(reportingSchemaId: $reportingSchemaId, filters: {id: {equal: $id}}) {
                id
                authorId
                assigneeId
                assignedGroupId
                reportingSchemaId
            }
        }
    """

    data = {}

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"id": id, "reportingSchemaId": reporting_schema_id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")
    task = data["data"]["tasks"][0]
    return GraphQLTask(
        id=task.get("id"),
        author_id=task.get("authorId"),
        assignee_id=task.get("assigneeId"),
        assigned_group_id=task.get("assignedGroupId"),
        reporting_schema_id=task.get("reportingSchemaId"),
    )


@cached(ttl=60, key_builder=cache_key_builder)
async def get_comment(task_id: str, id: str, token: str) -> "GraphQLComment":
    """
    Queries a comment from the Documentation Module and
    returns a GraphQLComment class instance
    """

    query = """
        query ($taskId: String!, $id: String!){
            comments(taskId: $taskId, filters: {id: {equal: $id}}) {
                id
                authorId
            }
        }
    """

    data = {}

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"id": id, "taskId": task_id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")
    comment = data["data"]["comments"][0]
    return GraphQLComment(
        id=comment.get("id"),
        author_id=comment.get("authorId"),
    )


@cached(ttl=60, key_builder=cache_key_builder)
async def get_source(project_id: str, id: str, token: str) -> "GraphQLProjectSource":
    """
    Queries a source from the Documentation Module and
    returns a GraphQLProjectSource class instance
    """

    query = """
        query($projectId: String!, $id: String) {
            projectSources(projectId: $projectId, filters: {id: {equal: $id}}) {
                id
                authorId
                projectId
            }
        }
    """

    data = {}

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"id": id, "projectId": project_id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")
    source = data["data"]["projectSources"][0]
    return GraphQLProjectSource(
        id=source.get("id"),
        project_id=source.get("projectId"),
        author_id=source.get("authorId"),
    )


@strawberry.federation.type(keys=["id"])
class GraphQLTask:
    id: strawberry.ID
    author: Annotated["GraphQLProjectMember", strawberry.lazy("schema.member")] = strawberry.field(resolver=get_author)
    author_id: str = strawberry.federation.field(shareable=True)
    assignee: Union[
        Annotated["GraphQLProjectMember", strawberry.lazy("schema.member")],
        Annotated["GraphQLProjectGroup", strawberry.lazy("schema.group")],
    ] = strawberry.field(resolver=get_assignee)
    assignee_id: Optional[str] = strawberry.federation.field(shareable=True)
    assigned_group_id: Optional[str] = strawberry.federation.field(shareable=True)
    reporting_schema_id: str = strawberry.federation.field(shareable=True)

    @classmethod
    async def resolve_reference(cls, info: Info, id: strawberry.ID):
        return await get_task("", id, get_token(info))


@strawberry.federation.type(keys=["id"])
class GraphQLProjectSource:
    id: strawberry.ID
    project_id: str = strawberry.federation.field(shareable=True)
    author: Annotated["GraphQLProjectMember", strawberry.lazy("schema.member")] = strawberry.field(resolver=get_author)
    author_id: str = strawberry.federation.field(shareable=True)

    @classmethod
    async def resolve_reference(cls, info: Info, id: strawberry.ID):
        return await get_source("", id, get_token(info))


@strawberry.federation.type(keys=["id"])
class GraphQLComment:
    id: strawberry.ID
    author: Optional[Annotated["GraphQLProjectMember", strawberry.lazy("schema.member")]] = strawberry.field(
        resolver=get_author
    )
    author_id: str = strawberry.federation.field(shareable=True)

    @classmethod
    async def resolve_reference(cls, info: Info, id: strawberry.ID):
        return await get_comment("", id, get_token(info))


async def delete_project_source(id: str, token: str):
    """Delete a project source"""

    query = """
        mutation($id: String!) {
            deleteProjectSource(id: $id) {
                id
            }
        }
    """

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"id": id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")
    return data["data"]["deleteProjectSource"]["id"]


async def delete_reporting_schema(id: str, token: str):
    """Delete a reporting schema"""

    query = """
        mutation($id: String!) {
            deleteReportingSchema(id: $id) {
                id
            }
        }
    """

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"id": id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")
    return data["data"]["deleteReportingSchema"]["id"]


async def get_reporting_schema(project_id: str, token: str) -> list[dict]:
    """
    Queries a source from the Documentation Module and
    returns a GraphQLReportingSchema class instance
    """

    query = """
        query($projectId: String!) {
            reportingSchemas(projectId: $projectId) {
                id
                projectId
            }
        }
    """

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"projectId": project_id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")

        return data.get("data", {}).get("reportingSchemas")


async def get_project_sources(project_id: str, token: str) -> list[dict]:
    """
    Queries a source from the Documentation Module and
    returns a GraphQLProjectSource class instance
    """

    query = """
        query($projectId: String!) {
            projectSources(projectId: $projectId) {
                id
                authorId
                projectId
            }
        }
    """

    async with httpx.AsyncClient(
        headers={"authorization": f"Bearer {token}"},
    ) as client:
        response = await client.post(
            f"{settings.ROUTER_URL}/graphql",
            json={
                "query": query,
                "variables": {"projectId": project_id},
            },
        )
        if response.is_error:
            raise MicroServiceConnectionError(f"Could not receive data from {settings.ROUTER_URL}. Got {response.text}")
        data = response.json()
        if errors := data.get("errors"):
            raise MicroServiceResponseError(f"Got error from {settings.ROUTER_URL}: {errors}")

        return data.get("data", {}).get("projectSources")
