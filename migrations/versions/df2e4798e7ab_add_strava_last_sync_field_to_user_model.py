"""Add strava_last_sync field to User model

Revision ID: df2e4798e7ab
Revises: d921a914ff0d
Create Date: 2024-02-05 23:05:40.788471

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df2e4798e7ab'
down_revision = 'd921a914ff0d'
branch_labels = None
depends_on = None


def upgrade():
    # Add strava_last_sync column to user table
    op.add_column('user', sa.Column('strava_last_sync', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    # Remove strava_last_sync column from user table
    op.drop_column('user', 'strava_last_sync')
