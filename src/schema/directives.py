import strawberry
from strawberry.schema_directive import Location


@strawberry.schema_directive(locations=[Location.OBJECT])
class Keys:
    fields: str
