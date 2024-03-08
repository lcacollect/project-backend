from typing import Optional

import strawberry
from lcacollect_config.graphql.input_filters import BaseFilter, FilterOptions


@strawberry.input
class ProjectMemberFilters(BaseFilter):
    user_id: Optional[FilterOptions] = None
    project_id: Optional[FilterOptions] = None
    name: Optional[FilterOptions] = None
    email: Optional[FilterOptions] = None
    company: Optional[FilterOptions] = None


@strawberry.input
class ProjectFilters(BaseFilter):
    domain: Optional[FilterOptions] = None
    name: Optional[FilterOptions] = None
    project_id: Optional[FilterOptions] = None
    id: Optional[FilterOptions] = None
    meta_fields: Optional[FilterOptions] = None


@strawberry.input
class ProjectGroupFilters(BaseFilter):
    name: Optional[FilterOptions] = None
    project_id: Optional[FilterOptions] = None
    id: Optional[FilterOptions] = None
