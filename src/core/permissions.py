from typing import Any

from aiocache import cached
from lcacollect_config.context import get_user
from lcacollect_config.exceptions import AuthenticationError
from lcacollect_config.validate import is_super_admin
from sqlmodel import select
from strawberry.permission import BasePermission
from strawberry.types import Info

import models.member as models_member


class IsProjectMember(BasePermission):
    message = "User is not authenticated"

    @cached(ttl=60)
    async def has_permission(self, source: Any, info: Info, **kwargs) -> bool:
        if user := get_user(info):
            if is_super_admin(user):
                return True
            query = (
                select(models_member.ProjectMember)
                .where(models_member.ProjectMember.user_id == user.claims.get("oid"))
                .where(models_member.ProjectMember.project_id == kwargs.get("projectId"))
            )
            session = info.context.get("session")
            project_members = await session.exec(query)
            if project_members.first():
                return True
            else:
                AuthenticationError(self.message)
        raise AuthenticationError(self.message)
