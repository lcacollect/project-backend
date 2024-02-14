import logging
from datetime import date
from typing import TYPE_CHECKING, Annotated, Optional

import strawberry
from fastapi import HTTPException
from lcacollect_config.context import get_session
from lcacollect_config.email import EmailType, send_email
from lcacollect_config.graphql.input_filters import filter_model_query
from lcacollect_config.user import (
    get_aad_user_by_email,
    get_users_from_azure,
    invite_user_to_aad,
)
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from strawberry.types import Info

import models.group as models_group
import models.member as models_member
import models.project as models_project
from core.validate import authenticate_user, project_exists
from exceptions import MSGraphException
from schema.inputs import ProjectMemberFilters

logger = logging.getLogger(__name__)

if TYPE_CHECKING:  # pragma: no cover
    from schema.group import GraphQLProjectGroup


@strawberry.federation.type(keys=["id"])
class GraphQLProjectMember:
    id: strawberry.ID
    user_id: str = strawberry.federation.field(shareable=True)
    name: str
    email: str = strawberry.federation.field(shareable=True)
    company: str | None
    last_login: date | None

    leader_of: list[Annotated["GraphQLProjectGroup", strawberry.lazy("schema.group")]] | None = None
    project_groups: list[Annotated["GraphQLProjectGroup", strawberry.lazy("schema.group")]] | None = None
    project_id: strawberry.ID


async def project_members_query(
    info: Info, project_id: str, filters: Optional[ProjectMemberFilters] = None
) -> list[GraphQLProjectMember]:
    """
    Query Project Members using ProjectID.
    Filters can be used to query unique members of the Project
    """

    session = get_session(info)
    await project_exists(session, project_id)

    query = (
        select(models_member.ProjectMember)
        .where(col(models_member.ProjectMember.project_id) == project_id)
        .options(selectinload(models_member.ProjectMember.leader_of))
        .options(selectinload(models_member.ProjectMember.project_groups))
    )
    if filters:
        query = filter_model_query(models_member.ProjectMember, filters, query)

    members = (await session.exec(query)).all()

    if not members:
        return []

    user_ids = [member.user_id for member in members]

    if not user_ids:
        return []
    try:
        users = await get_users_from_azure(user_ids)
    except MSGraphException:
        logger.exception("User not found in azure Entra ID")
        users = []

    return [
        GraphQLProjectMember(
            id=member.id,
            project_id=member.project_id,
            leader_of=member.leader_of,
            project_groups=member.project_groups,
            **get_user_info(users, member.user_id),
        )
        for member in members
    ]


def get_user_info(users, user_id: str) -> dict:
    """
    Extract user information from Azure Active Directory
    """

    found_users = [_user for _user in users if _user.get("user_id") == user_id]
    if found_users:
        return found_users[0]
    return {"user_id": "", "name": "", "email": "", "company": None, "last_login": None}


async def add_project_member_mutation(
    info: Info, name: str, email: str, project_id: str, project_group_ids: list[str]
) -> GraphQLProjectMember:
    """Add a Project Member"""

    session: AsyncSession = info.context.get("session")
    await project_exists(session, project_id)

    # get the platform url
    request: Request = info.context.get("request")
    origin_url = request.headers.get("origin")
    # check if user exists in organization's Azure Active Directory tenant
    user = await get_aad_user_by_email(email)
    user_id = user.get("id")
    if not user_id:
        # if doesn't exist - invite user to organization's AD
        response = invite_user_to_aad(email, name, origin_url)
        if not response.ok:
            raise HTTPException(500, f"Unable to add user to Azure AD: {response.text}")
        data: dict = response.json()
        user_id = data.get("invitedUser", {}).get("id")
        if not user_id:
            raise HTTPException(
                500,
                f"Failed to fetch user_id value from invitation response for invited user:{response.text}",
            )

    # check if user is already member of the project
    query = select(models_member.ProjectMember).where(
        models_member.ProjectMember.user_id == user_id,
        models_member.ProjectMember.project_id == project_id,
    )
    project_member_exists = await session.exec(query)
    if project_member_exists.all():
        raise AttributeError(f"Member with email '{email}' already exists - adding existing user to project")
    for member in project_member_exists:
        _ = await authenticate_user(info, member.project_id)
    groups: list[models_group.ProjectGroup] = (
        await session.exec(
            select(models_group.ProjectGroup).where(col(models_group.ProjectGroup.id).in_(project_group_ids))
        )
    ).all()

    project_member = models_member.ProjectMember(user_id=user_id, project_id=project_id, project_groups=groups)

    session.add(project_member)

    await session.commit()

    project = await session.get(models_project.Project, project_id)

    # send email notification
    info.context["background_tasks"].add_task(
        send_email, email, EmailType.INVITE_TO_LCA, **{"project_name": project.name, "url": origin_url}
    )

    user = await get_users_from_azure(user_id)

    gql_pm = GraphQLProjectMember(
        id=project_member.id,
        project_id=project_member.project_id,
        project_groups=groups,
        **user[0],
    )
    return gql_pm


async def delete_project_member_mutation(info: Info, id: str) -> str:
    """Delete a Project Member"""

    session = info.context.get("session")
    project_member = await session.get(models_member.ProjectMember, id)
    _ = await authenticate_user(info, project_member.project_id)
    await session.delete(project_member)
    await session.commit()
    return id
