"""empty message

Revision ID: e553f35142f3
Revises: 2bd9ea5c3ec5
Create Date: 2020-09-06 12:36:26.031395

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'e553f35142f3'
down_revision = '2bd9ea5c3ec5'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('aliases',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('server_id', mysql.BIGINT(unsigned=True), nullable=True),
    sa.Column('alias', sa.String(), nullable=True),
    sa.Column('command', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('aliases')
    # ### end Alembic commands ###
