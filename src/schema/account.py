import strawberry
from lcaconfig.context import get_user
from strawberry.types import Info


@strawberry.type
class GraphQLUserAccount:
    id: str
    tenant_id: str
    name: str
    roles: list[str]
    email: str


async def account_query(info: Info) -> GraphQLUserAccount:
    """Get current user"""

    account = get_user(info)
    return GraphQLUserAccount(
        id=account.claims.get("oid", ""),
        tenant_id=account.tid,
        name=account.name,
        roles=account.roles,
        email=account.claims.get("preferred_username", ""),
    )
