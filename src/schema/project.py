import base64
import logging
from enum import Enum
from hashlib import sha256
from typing import Optional

import strawberry
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.storage.blob.aio import BlobClient
from fastapi import BackgroundTasks
from lcacollect_config.context import get_session, get_token, get_user
from lcacollect_config.exceptions import AuthenticationError, DatabaseItemNotFound
from lcacollect_config.graphql.input_filters import FilterOptions, filter_model_query
from lcacollect_config.validate import is_super_admin
from sqlalchemy.orm import selectinload
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession
from strawberry.scalars import JSON
from strawberry.types import Info

import models.member as models_member
import models.project as models_project
import schema.group as schema_group
import schema.member
import schema.member as schema_member
from core.config import settings
from core.federation import (
    delete_project_source,
    delete_reporting_schema,
    get_project_sources,
    get_reporting_schema,
)
from schema.directives import Keys
from schema.inputs import ProjectFilters, ProjectMemberFilters
from schema.stage import GraphQLProjectStage

logger = logging.getLogger(__name__)


@strawberry.enum
class ProjectDomain(Enum):
    infrastructure = "Infrastructure"
    energy = "Energy"
    buildings = "Buildings"
    tunnels = "Tunnels"


@strawberry.federation.type(directives=[Keys(fields="project_id")])
class GraphQLProject:
    id: str
    project_id: strawberry.ID | None
    name: str
    client: str | None
    domain: ProjectDomain | None
    address: str | None
    city: str | None
    country: str | None
    image_url: str | None
    meta_fields: Optional[JSON]

    groups: list[schema_group.GraphQLProjectGroup] | None
    stages: list[GraphQLProjectStage] | None
    members: list[schema_member.GraphQLProjectMember] | None


@strawberry.input
class ProjectMemberInput:
    user_id: str


@strawberry.input
class ProjectGroupInput:
    id: str
    name: str
    lead_id: str


@strawberry.input
class LifeCycleStageInput:
    stage_id: str


async def projects_query(info: Info, filters: Optional[ProjectFilters] = None) -> list[GraphQLProject]:
    """Query all Projects user has access to"""

    session = get_session(info)
    user = get_user(info)

    if is_super_admin(user):
        query = (
            select(models_project.Project)
            .options(selectinload(models_project.Project.groups))
            .options(selectinload(models_project.Project.stages))
            .options(selectinload(models_project.Project.members))
        )
    else:
        query = (
            select(models_project.Project)
            .where(models_member.ProjectMember.user_id == user.claims.get("oid"))
            .join(models_member.ProjectMember)
            .options(selectinload(models_project.Project.groups))
            .options(selectinload(models_project.Project.stages))
            .options(selectinload(models_project.Project.members))
        )

    if filters:
        query = filter_model_query(models_project.Project, filters, query)
    authorized_projects = (await session.exec(query)).all()
    if not authorized_projects:
        return []

    if (
        any(selection.name in "members" for field in info.selected_fields for selection in field.selections)
        and authorized_projects[0].members is not None
    ):
        updated_projects = []
        for project in authorized_projects:
            member_ids = list({member.id for member in project.members})
            project_members = []
            for member_id in member_ids:
                project_member = await schema.member.project_members_query(
                    info,
                    project.id,
                    filters=ProjectMemberFilters(user_id=FilterOptions(contains=member_id)),
                )
                project_members.append(project_member)
            updated_projects.append(
                GraphQLProject(
                    **project.dict(),
                    members=project_members,
                    groups=project.groups,
                    stages=project.stages,
                )
            )
        return updated_projects

    return authorized_projects


async def add_project_mutation(
    info: Info,
    name: str,
    project_id: Optional[str] = None,
    client: Optional[str] = None,
    domain: Optional[ProjectDomain] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    file: Optional[str] = None,
    members: Optional[list[ProjectMemberInput]] = None,
    groups: Optional[list[ProjectGroupInput]] = None,
    stages: Optional[list[LifeCycleStageInput]] = None,
    meta_fields: Optional[JSON] = None,
) -> GraphQLProject:
    """Add a Project"""

    if meta_fields is None:
        meta_fields = {}

    session: AsyncSession = info.context.get("session")

    project = models_project.Project(
        name=name,
        project_id=project_id,
        client=client,
        domain=domain,
        city=city,
        country=country,
        address=address,
        meta_fields=meta_fields,
    )
    if file:
        project.image_url = await handle_file_upload(file)

    session.add(project)

    if members:
        for index, member in enumerate(members):
            project_member = models_member.ProjectMember(
                user_id=member.user_id,
                project=project,
                project_id=project_id,
            )
            session.add(project_member)
            if index == 0:
                project.meta_fields.update({"owner": member.user_id})

    if stages:
        for stage in stages:
            stage_link = models_project.ProjectStage(project=project, stage_id=stage.stage_id)
            session.add(stage_link)

    if groups:
        for group in groups:
            group_link = models_project.ProjectGroup(project=project, **group.dict(exclude_unset=True))
            session.add(group_link)

    await session.commit()
    await session.refresh(project)

    query = (
        select(models_project.Project)
        .where(col(models_project.Project.id) == project.id)
        .options(selectinload(models_project.Project.groups))
        .options(selectinload(models_project.Project.stages))
        .options(selectinload(models_project.Project.members))
    )
    await session.exec(query)

    return project


async def update_project_mutation(
    info: Info,
    id: str,
    project_id: Optional[str] = None,
    name: Optional[str] = None,
    address: Optional[str] = None,
    city: Optional[str] = None,
    country: Optional[str] = None,
    client: Optional[str] = None,
    domain: Optional[ProjectDomain] = None,
    file: Optional[str] = None,
    meta_fields: Optional[JSON] = None,
) -> GraphQLProject:
    """Update a Project"""

    session = await authenticate_user(id, info)

    if meta_fields is None:
        meta_fields = {}

    project = await session.get(models_project.Project, id)
    if not project:
        raise DatabaseItemNotFound(f"Could not find project with id: {id}")

    kwargs = {
        "name": name,
        "project_id": project_id,
        "client": client,
        "domain": domain.name if domain else None,
        "meta_fields": meta_fields,
        "address": address,
        "city": city,
        "country": country,
    }
    if file:
        image_url = await handle_file_upload(file)
        kwargs["image_url"] = image_url

    for key, value in kwargs.items():
        if value and key != "meta_fields":
            setattr(project, key, value)
        if value and key == "meta_fields":
            fields = {**project.meta_fields, **value}
            project.meta_fields = fields

    session.add(project)

    await session.commit()
    await session.refresh(project)
    query = (
        select(models_project.Project)
        .options(selectinload(models_project.Project.groups))
        .options(selectinload(models_project.Project.stages))
        .options(selectinload(models_project.Project.members))
        .where(models_project.Project.id == project.id)
    )
    project: models_project.Project = (await session.exec(query)).first()

    member_ids = list({member.id for member in project.members})
    if member_ids:
        project_members = []
        for member_id in member_ids:
            project_member = await schema.member.project_members_query(
                info,
                project.id,
                filters=ProjectMemberFilters(user_id=FilterOptions(contains=member_id)),
            )
            project_members.append(project_member)
    else:
        project_members = None
    return GraphQLProject(
        **project.dict(),
        members=project_members,
        groups=project.groups,
        stages=project.stages,
    )


async def delete_project_mutation(info: Info, id: str) -> str:
    """Delete a project"""

    session = await authenticate_user(id, info)
    project = await session.get(models_project.Project, id)
    if not project:
        raise DatabaseItemNotFound(f"Could not find project with id: {id}")
    background: BackgroundTasks = info.context.get("background_tasks")
    background.add_task(delete_reporting_schema_and_source, get_token(info), project.id)

    await session.delete(project)
    await session.commit()
    return id


async def delete_reporting_schema_and_source(token: str, project_id: str):
    """Delete reporting schema and Project Source after project is deleted"""

    reporting_schemas = await get_reporting_schema(project_id, token)
    project_sources = await get_project_sources(project_id, token)
    if reporting_schemas:
        for schema in reporting_schemas:
            _ = await delete_reporting_schema(schema.get("id"), token)
    if project_sources:
        for source in project_sources:
            _ = await delete_project_source(source.get("id"), token)


async def handle_file_upload(file: str) -> str:
    data = base64.b64decode(file)
    file_path = await upload_to_storage_account(data)
    return f"{settings.STORAGE_ACCOUNT_URL.strip('/')}/" f"{settings.STORAGE_CONTAINER_NAME.strip('/')}/" f"{file_path}"


async def upload_to_storage_account(data: str | bytes) -> str:
    """
    Upload file to Azure Storage Account Blob Container

    Returns
    -------
    path to the file in blob container.
    path is constructed as follows:
    `hash/{sha256[:2]}/{hash_str[2:4]}/{hash_str[4:]}`
    where sha256 is sha256 hash of the input string
    """

    if not isinstance(data, bytes):
        data = data.encode()
    hash_str = sha256(data).hexdigest()
    filepath = f"{settings.STORAGE_BASE_PATH}/{hash_str[:2]}/{hash_str[2:4]}/{hash_str[4:]}"

    async with BlobClient(
        account_url=settings.STORAGE_ACCOUNT_URL,
        container_name=settings.STORAGE_CONTAINER_NAME,
        credential=settings.STORAGE_ACCESS_KEY,
        blob_name=filepath,
    ) as blob:
        try:
            await blob.upload_blob(data)
        except ResourceExistsError:
            return filepath
        except ResourceNotFoundError as error:
            logger.error(
                f"Could not upload file to Azure Storage Container: "
                f"{settings.STORAGE_ACCOUNT_URL}/{settings.STORAGE_CONTAINER_NAME}"
            )
            raise

    return filepath


async def authenticate_user(id, info):
    """Authenticates the user trying to mutate/query"""

    session = info.context.get("session")
    user = info.context.get("user")

    projects_query = (
        select(models_project.Project)
        .join(models_member.ProjectMember)
        .where(
            models_member.ProjectMember.user_id == user.claims.get("oid"),
            models_project.Project.id == id,
        )
    )
    authenticated_project = await session.exec(projects_query)

    if not authenticated_project:
        raise AuthenticationError
    return session
