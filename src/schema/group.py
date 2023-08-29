from typing import TYPE_CHECKING, Annotated, Optional

import strawberry
from lcacollect_config.context import get_session
from lcacollect_config.exceptions import DatabaseItemNotFound
from lcacollect_config.graphql.input_filters import filter_model_query
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select
from strawberry.types import Info

import models.group as models_group
import models.member as models_member
from core.validate import authenticate_user, project_exists
from schema.inputs import ProjectGroupFilters

if TYPE_CHECKING:  # pragma: no cover
    from schema.member import GraphQLProjectMember


@strawberry.federation.type(keys=["id"])
class GraphQLProjectGroup:
    id: strawberry.ID
    name: str
    lead_id: str | None
    lead: Annotated["GraphQLProjectMember", strawberry.lazy("schema.member")] | None
    members: list[Annotated["GraphQLProjectMember", strawberry.lazy("schema.member")]] | None
    project_id: str


async def get_project_groups_query(
    info: Info, project_id: str, filters: Optional[ProjectGroupFilters] = None
) -> list[GraphQLProjectGroup]:
    """Query all Project Groups"""

    session = await authenticate_user(info, project_id, check_public=True)

    if not await project_exists(session, project_id):
        raise DatabaseItemNotFound(f"Project with id: {project_id} does not exist")

    query = (
        select(models_group.ProjectGroup)
        .where(models_group.ProjectGroup.project_id == project_id)
        .options(selectinload(models_group.ProjectGroup.members))
    )
    query = graphql_group_options(info, query)
    if filters:
        query = filter_model_query(models_group.ProjectGroup, filters, query)
    groups = (await session.exec(query)).all()

    return [await handle_members_and_lead(info, group) for group in groups]


async def add_project_group_mutation(
    info: Info, project_id: str, name: str, lead_id: str | None = None
) -> GraphQLProjectGroup:
    """Add a Project Group"""

    session = await authenticate_user(info, project_id)

    if not await project_exists(session, project_id):
        raise DatabaseItemNotFound(f"Project with id: {project_id} does not exist")

    group = models_group.ProjectGroup(name=name, project_id=project_id, lead_id=lead_id)

    session.add(group)
    await session.commit()

    query = select(models_group.ProjectGroup).where(
        models_group.ProjectGroup.project_id == project_id,
        models_group.ProjectGroup.name == name,
    )
    query = graphql_group_options(info, query)
    group = (await session.exec(query)).first()
    return await handle_members_and_lead(info, group)


async def update_project_group_mutation(
    info: Info, id: str, name: Optional[str] = None, lead_id: Optional[str] = None
) -> GraphQLProjectGroup:
    """Update a Project Group"""

    session = get_session(info)
    group = await session.get(models_group.ProjectGroup, id)
    _ = await authenticate_user(info, group.project_id)

    if not group:
        raise DatabaseItemNotFound(f"Could not find a project group with id: {id}")

    kwargs = {"name": name, "lead_id": lead_id}

    for key, value in kwargs.items():
        if value:
            setattr(group, key, value)

    session.add(group)
    await session.commit()

    query = select(models_group.ProjectGroup).where(models_group.ProjectGroup.id == id)
    query = graphql_group_options(info, query)

    group = (await session.exec(query)).first()
    return await handle_members_and_lead(info, group)


async def delete_project_group_mutation(info: Info, id: str) -> str:
    """Delete a project group"""

    session: AsyncSession = info.context.get("session")
    group = await session.get(models_group.ProjectGroup, id)
    if not group:
        raise DatabaseItemNotFound(f"Could not find a project group with id: {id}")
    _ = await authenticate_user(info, group.project_id)
    await session.delete(group)
    await session.commit()
    return id


async def add_project_members_to_group_mutation(
    info: Info, group_id: str, member_ids: list[str]
) -> GraphQLProjectGroup:
    """Add Project Members to an existing Project Group"""

    session: AsyncSession = info.context.get("session")

    group: models_group.ProjectGroup = (
        await session.exec(
            select(models_group.ProjectGroup)
            .where(models_group.ProjectGroup.id == group_id)
            .options(selectinload(models_group.ProjectGroup.members))
        )
    ).first()
    if not group:
        raise DatabaseItemNotFound(f"could find a project group with id: {group_id}")

    _ = await authenticate_user(info, group.project_id)
    # add new members to group
    for member_id in member_ids:
        member = await session.get(models_member.ProjectMember, member_id)
        if member not in group.members:
            group.members.append(member)

    session.add(group)
    await session.commit()
    await session.refresh(group)

    return await handle_members_and_lead(info, group)


async def remove_project_members_from_group_mutation(
    info: Info, group_id: str, member_ids: list[str]
) -> GraphQLProjectGroup:
    """Remove Project Members from an existing Project Group"""

    session: AsyncSession = info.context.get("session")

    group: models_group.ProjectGroup = (
        await session.exec(
            select(models_group.ProjectGroup)
            .where(models_group.ProjectGroup.id == group_id)
            .options(selectinload(models_group.ProjectGroup.members))
        )
    ).first()
    if not group:
        raise DatabaseItemNotFound(f"could find a project group with id: {group_id}")

    _ = await authenticate_user(info, group.project_id)
    for member_id in member_ids:
        member: models_member.ProjectMember = (
            await session.exec(
                select(models_member.ProjectMember)
                .where(models_member.ProjectMember.project_id == group.project_id)
                .where(models_member.ProjectMember.id == member_id)
            )
        ).first()
        group.members.remove(member)

    session.add(group)
    await session.commit()
    await session.refresh(group)

    lead = await session.get(models_member.ProjectMember, group.lead_id)
    members = []
    if group.members:
        for group_member in group.members:
            member = await session.get(models_member.ProjectMember, group_member.id)
            members.append(member)
    else:
        members = group.members
    group = GraphQLProjectGroup(**group.dict(), lead=lead, members=members)
    return group


def graphql_group_options(info: Info, query: Select) -> Select:
    """
    Optionally "select IN" loads the needed collections of a Project Group
    based on the request provided in the info

    Args:
        info (Info): request information
        query: current query provided

    Returns: updated query
    """

    if any(selection.name in "lead" for field in info.selected_fields for selection in field.selections):
        query = query.options(selectinload(models_group.ProjectGroup.lead))

    if any(selection.name in "members" for field in info.selected_fields for selection in field.selections):
        query = query.options(selectinload(models_group.ProjectGroup.members))
    return query


async def handle_members_and_lead(info: Info, group: models_group.ProjectGroup):
    """Handle fetching data about lead and project members, if it is required in the query/mutation"""

    from lcacollect_config.user import get_users_from_azure

    from schema.member import GraphQLProjectMember, get_user_info

    session = get_session(info)
    # if neither lead nor members were requested return group as is
    if not any(
        selection.name in ("members", "lead") for field in info.selected_fields for selection in field.selections
    ):
        return group

    members = []
    lead = None

    # if members are requested get a list of GraphQLProjectMember
    if member_selection := [
        selection for field in info.selected_fields for selection in field.selections if selection.name in "members"
    ]:
        if group.members:
            for group_member in group.members:
                member = await session.get(models_member.ProjectMember, group_member.id)
                members.append(member)
            if any(
                [
                    selection.name in ["name", "email", "company", "last_login"]
                    for field in member_selection
                    for selection in field.selections
                ]
            ):
                users = await get_users_from_azure([member.user_id for member in members])
                members = [
                    GraphQLProjectMember(
                        id=member.id,
                        project_id=member.project_id,
                        leader_of=None,
                        project_groups=None,
                        **get_user_info(users, member.user_id),
                    )
                    for member in members
                ]
        else:
            members = []

    # if lead is requested get GraphQLProjectMember
    if lead_selection := [
        selection for field in info.selected_fields for selection in field.selections if selection.name in "lead"
    ]:
        lead = await session.get(models_member.ProjectMember, group.lead_id)
        if lead and any(
            [
                selection.name in ["name", "email", "company", "last_login"]
                for field in lead_selection
                for selection in field.selections
            ]
        ):
            users = await get_users_from_azure(lead.user_id)
            lead = GraphQLProjectMember(
                id=lead.id,
                project_id=lead.project_id,
                leader_of=None,
                project_groups=None,
                **get_user_info(users, lead.user_id),
            )
    # Construct instance of GraphQLProjectGroup
    group = GraphQLProjectGroup(**group.dict(), lead=lead, members=members)

    return group
