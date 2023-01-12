import json
import re
from datetime import date, datetime
from typing import TYPE_CHECKING, Annotated, Optional

import strawberry
from aiocache import cached, caches
from fastapi import HTTPException
from lcaconfig.graphql.input_filters import filter_model_query
from msgraph.core import GraphClient
from requests import Response
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request
from strawberry.types import Info

import models.group as models_group
import models.member as models_member
import models.project as models_project
from core.config import settings
from core.validate import authenticate_user, project_exists
from schema.inputs import ProjectMemberFilters

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

    session = info.context.get("session")
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

    users = await get_users_from_azure(user_ids)

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
    return {"user_id": "", "name": "", "email": "", "company": "", "last_login": ""}


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
    info.context["background_tasks"].add_task(send_email, email, project.name, origin_url)

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


async def get_aad_user_by_email(email: str) -> dict[str, str]:
    """Check if user exists in Azure Active Directory"""
    cache = caches.get("azure_users")
    user_data = await cache.get(email, namespace="azure_emails")
    if user_data:
        return user_data

    graph = GraphClient(credential=settings.AAD_GRAPH_CREDENTIAL)
    headers = {"Content-Type": "application/json"}

    # construct user principal name
    user_principal_name = email
    # check if user is an external user
    if not any(domain in email for domain in settings.INTERNAL_EMAIL_DOMAINS_LIST):
        # externals have principal name formatted like
        # xxxx_gmail.com%23EXT%23@cowi.onmicrosoft.com
        user_principal_name = user_principal_name.replace("@", "_")
        user_principal_name += f"%23EXT%23@{settings.DEFAULT_AD_FQDN}"
    response = graph.get(url=f"/users/{user_principal_name}", headers=headers)

    data = response.json()
    await cache.add(email, data, namespace="azure_emails", ttl=60 * 5)
    return data


def invite_user_to_aad(email: str, name: str, platform_url: str) -> Response:
    """
    invites a user to organization's Active Directory

    Parameters
    ----------
    email: str
        user's email to create an AD account and send invitation to
    name: str
        name to be displayed on AD and on the platform
    platform_url: str
        platform url that the invitation will redirect to

    Returns
    -------
    response: requests.Response
        http response received from Graph API
    """

    graph = GraphClient(credential=settings.AAD_GRAPH_CREDENTIAL)

    headers = {"Content-Type": "application/json"}

    body = {
        "invitedUserEmailAddress": email,
        "inviteRedirectUrl": platform_url,
        "invitedUserDisplayName": name,
        "sendInvitationMessage": True,
        "userPrincipalName": email,
    }
    # add user
    response = graph.post(url=f"/invitations", data=json.dumps(body), headers=headers)
    return response


async def get_users_from_azure(user_ids: str | list[str]) -> list[dict[str, str]]:
    """Fetch Users from Azure Active Directory"""

    if not user_ids:
        return [{}]

    if not isinstance(user_ids, list):
        user_ids = [user_ids]

    cache = caches.get("azure_users")
    user_data = await cache.multi_get(user_ids, namespace="azure_users")
    users = {user_id: user_data[index] for index, user_id in enumerate(user_ids)}
    missing_users = [user_id for user_id, user_data in users.items() if user_data is None]

    requests = []
    headers = {"Content-Type": "application/json"}
    for user_id in missing_users:
        # graph api Beta supports signInActivity
        request = {
            "id": f"{user_id}",
            "method": "GET",
            "url": f"/users/{user_id}?$select=id,displayName,mail," "userPrincipalName,companyName,signInActivity",
            # signInActivity field requires AuditLog.Read.All permission
            "headers": headers,
        }

        requests.append(request)
    if requests:
        graph = GraphClient(credential=settings.AAD_GRAPH_CREDENTIAL)
        # use /beta/$batch url if fetching signInActivity
        responses = graph.post(
            url="https://graph.microsoft.com/beta/$batch",
            data=json.dumps({"requests": requests}),
            headers=headers,
        )
        if not responses.status_code == 200:
            raise HTTPException(500, f"Failed to fetch users via Graph API: {responses.text}")

        data: dict[str, list[dict]] = responses.json()

        for response in data.get("responses"):
            if not response.get("status") == 200:
                raise HTTPException(500, f"Failed to fetch the response from responses: {response}")
            body: dict[str, str] = response.get("body")
            email = body.get("mail")
            # some accounts have null emails
            if not email:
                if re.match(
                    r"^([a-zA-Z0-9_\-\.]+)@([a-zA-Z0-9_\-\.]+)\.([a-zA-Z]{2,5})$",
                    body.get("userPrincipalName"),
                ):
                    email = body.get("userPrincipalName")
                else:
                    email = "NA"
            if last_login := body.get("signInActivity", {}).get("lastSignInDateTime"):
                last_login = datetime.strptime(last_login, r"%Y-%m-%dT%H:%M:%SZ").date()
            users[body.get("id")] = {
                "user_id": body.get("id"),
                "name": body.get("displayName"),
                "email": email,
                "company": body.get("companyName"),
                "last_login": last_login,
            }
        await cache.multi_set(pairs=users.items(), ttl=60 * 5, namespace="azure_users")
    return list(users.values())


async def send_email(recepient: str, project_name: str, url: str) -> None:
    """
    Send an email invitation to the LCA Platform using Sendgrid

    Parameters
    ----------
    recepient: str
        email address of recipient
    project_name: str
        project name to display in email
        invitation
    url: str
        platform url to display in invitation
    """

    message_body = (
        "Hello,\n"
        f'You have been invited to project "{project_name}" on LCA Platform.\n'
        f"You can now access it via {url}\n"
        "With best regards, LCAcollect team.\n"
        "This email was generated automatically"
    )
    message = Mail(
        from_email=settings.EMAIL_NOTIFICATION_FROM,
        to_emails=recepient,
        subject="LCA: You have been invited to a project",
        plain_text_content=message_body,
    )

    sg = SendGridAPIClient(settings.SENDGRID_SECRET)
    sg.send(message)
