from lcacollect_config.context import get_session, get_user
from lcacollect_config.exceptions import AuthenticationError, DatabaseItemNotFound
from lcacollect_config.validate import is_super_admin
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession
from strawberry.types import Info

from models.member import ProjectMember
from models.project import Project


async def project_exists(session: AsyncSession, project_id: str) -> bool:

    """Check that a project exists in the database"""

    if not await session.get(Project, project_id):
        raise DatabaseItemNotFound(f"Project with id: {project_id} does not exist")
    return True


async def authenticate_user(info: Info, project_id: str) -> AsyncSession:

    """Check that user has access to project data"""

    session = get_session(info)
    user = get_user(info)
    if is_super_admin(user):
        return session

    query = (
        select(Project)
        .join(ProjectMember)
        .where(
            ProjectMember.user_id == user.claims.get("oid"),
            Project.id == project_id,
        )
    )
    authenticated_project = await session.exec(query)
    if not authenticated_project:
        raise AuthenticationError

    return session
