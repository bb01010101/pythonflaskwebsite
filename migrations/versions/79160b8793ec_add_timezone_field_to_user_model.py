"""Add timezone field to User model

Revision ID: 79160b8793ec
Revises: 5c49b4fb822d
Create Date: 2024-12-23 23:01:57.841633

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79160b8793ec'
down_revision = '5c49b4fb822d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.String(length=50), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('timezone')

    # ### end Alembic commands ###
