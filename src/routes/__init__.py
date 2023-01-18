import os

from lcacollect_config.fastapi import get_context
from lcacollect_config.router import LCAGraphQLRouter

from schema import schema

graphql_app = LCAGraphQLRouter(
    schema,
    context_getter=get_context,
    path="/graphql",
    graphiql=os.getenv("SERVER_NAME") == "LCA Dev",
)
