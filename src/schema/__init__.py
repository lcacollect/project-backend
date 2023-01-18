from inspect import getdoc

import strawberry
from lcacollect_config.permissions import IsAuthenticated

import schema.account as schema_account
import schema.group as schema_group
import schema.member as schema_member
import schema.project as schema_project
import schema.stage as schema_stage
from core.federation import GraphQLComment, GraphQLProjectSource, GraphQLTask
from core.permissions import IsProjectMember


@strawberry.type
class Query:

    """GraphQL Queries"""

    account: schema_account.GraphQLUserAccount = strawberry.field(
        permission_classes=[IsAuthenticated],
        resolver=schema_account.account_query,
        description=getdoc(schema_account.account_query),
    )
    projects: list[schema_project.GraphQLProject] = strawberry.field(
        permission_classes=[IsAuthenticated],
        resolver=schema_project.projects_query,
        description=getdoc(schema_project.projects_query),
    )
    project_members: list[schema_member.GraphQLProjectMember] = strawberry.field(
        permission_classes=[IsProjectMember],
        resolver=schema_member.project_members_query,
        description=getdoc(schema_member.project_members_query),
    )
    life_cycle_stages: list[schema_stage.GraphQLLifeCycleStage] = strawberry.field(
        resolver=schema_stage.get_life_cycle_stages_query,
        description=getdoc(schema_stage.get_life_cycle_stages_query),
    )
    project_stages: list[schema_stage.GraphQLProjectStage] = strawberry.field(
        permission_classes=[IsAuthenticated],
        resolver=schema_stage.get_project_stages_query,
        description=getdoc(schema_stage.get_project_stages_query),
    )
    project_groups: list[schema_group.GraphQLProjectGroup] = strawberry.field(
        permission_classes=[IsProjectMember],
        resolver=schema_group.get_project_groups_query,
        description=getdoc(schema_group.get_project_groups_query),
    )


@strawberry.type
class Mutation:
    """GraphQL Mutations"""

    # Project
    add_project: schema_project.GraphQLProject = strawberry.mutation(
        permission_classes=[IsAuthenticated],
        resolver=schema_project.add_project_mutation,
        description=getdoc(schema_project.add_project_mutation),
    )
    update_project: schema_project.GraphQLProject = strawberry.mutation(
        permission_classes=[IsAuthenticated],
        resolver=schema_project.update_project_mutation,
        description=getdoc(schema_project.update_project_mutation),
    )
    delete_project: str = strawberry.mutation(
        permission_classes=[IsAuthenticated],
        resolver=schema_project.delete_project_mutation,
        description=getdoc(schema_project.delete_project_mutation),
    )

    # Project Members
    add_project_member: schema_member.GraphQLProjectMember = strawberry.mutation(
        permission_classes=[IsProjectMember],
        resolver=schema_member.add_project_member_mutation,
        description=getdoc(schema_member.add_project_member_mutation),
    )
    delete_project_member: str = strawberry.mutation(
        permission_classes=[IsAuthenticated],
        resolver=schema_member.delete_project_member_mutation,
        description=getdoc(schema_member.delete_project_member_mutation),
    )

    # Project Stages
    add_project_stage: schema_stage.GraphQLProjectStage = strawberry.field(
        permission_classes=[IsProjectMember],
        resolver=schema_stage.add_project_stage_mutation,
        description=getdoc(schema_stage.add_project_stage_mutation),
    )
    delete_project_stage: str = strawberry.field(
        permission_classes=[IsProjectMember],
        resolver=schema_stage.delete_project_stage_mutation,
        description=getdoc(schema_stage.delete_project_stage_mutation),
    )

    # Project Groups
    add_project_group: schema_group.GraphQLProjectGroup = strawberry.field(
        permission_classes=[IsProjectMember],
        resolver=schema_group.add_project_group_mutation,
        description=getdoc(schema_group.add_project_group_mutation),
    )

    update_project_group: schema_group.GraphQLProjectGroup = strawberry.field(
        permission_classes=[IsAuthenticated],
        resolver=schema_group.update_project_group_mutation,
        description=getdoc(schema_group.update_project_group_mutation),
    )

    delete_project_group: str = strawberry.field(
        permission_classes=[IsAuthenticated],
        resolver=schema_group.delete_project_group_mutation,
        description=getdoc(schema_group.delete_project_group_mutation),
    )
    add_project_members_to_group: schema_group.GraphQLProjectGroup = strawberry.mutation(
        permission_classes=[IsAuthenticated],
        resolver=schema_group.add_project_members_to_group_mutation,
        description=getdoc(schema_group.add_project_members_to_group_mutation),
    )
    remove_project_members_from_group: schema_group.GraphQLProjectGroup = strawberry.mutation(
        permission_classes=[IsAuthenticated],
        resolver=schema_group.remove_project_members_from_group_mutation,
        description=getdoc(schema_group.remove_project_members_from_group_mutation),
    )


schema = strawberry.federation.Schema(
    query=Query,
    mutation=Mutation,
    enable_federation_2=True,
    types=[GraphQLTask, GraphQLProjectSource, GraphQLComment],
)
