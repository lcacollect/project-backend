"""empty message

Revision ID: 04d0b0be673d
Revises: ee61906c1705
Create Date: 2023-08-28 10:51:56.240513

"""
import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "04d0b0be673d"
down_revision = "ee61906c1705"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "project", sa.Column("public", sa.Boolean(), nullable=False, server_default=sa.sql.expression.false())
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("project", "public")
    # ### end Alembic commands ###