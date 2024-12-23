"""Remove timezone field from User model

Revision ID: c2a371bd108f
Revises: 79160b8793ec
Create Date: 2024-12-23 23:04:52.762842

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c2a371bd108f'
down_revision = '79160b8793ec'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('timezone')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('timezone', sa.VARCHAR(length=50), autoincrement=False, nullable=True))

    # ### end Alembic commands ###
