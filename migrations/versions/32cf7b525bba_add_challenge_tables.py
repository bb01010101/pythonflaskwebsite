"""Add challenge tables

Revision ID: 32cf7b525bba
Revises: a9491326a1d6
Create Date: 2024-12-29 18:35:22.721935

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '32cf7b525bba'
down_revision = 'a9491326a1d6'
branch_labels = None
depends_on = None


def upgrade():
    # Create challenge table
    op.create_table('challenge',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('creator_id', sa.Integer(), nullable=False),
        sa.Column('metric_type', sa.String(length=50), nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=False),
        sa.Column('is_public', sa.Boolean(), nullable=True, default=True),
        sa.Column('invite_code', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['creator_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['metric_id'], ['custom_metric.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Create challenge_participant table
    op.create_table('challenge_participant',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.Integer(), nullable=False),
        sa.Column('joined_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['challenge_id'], ['challenge.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # Drop old tables
    op.execute('DROP TABLE IF EXISTS challenge_message CASCADE')
    op.execute('DROP TABLE IF EXISTS challenge_post_comment CASCADE')
    op.execute('DROP TABLE IF EXISTS challenge_post_like CASCADE')
    op.execute('DROP TABLE IF EXISTS challenge_post CASCADE')


def downgrade():
    # Drop new tables
    op.drop_table('challenge_participant')
    op.drop_table('challenge')
