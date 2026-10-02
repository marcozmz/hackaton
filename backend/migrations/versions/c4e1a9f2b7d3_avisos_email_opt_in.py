"""avisos por e-mail: user.email_alerts_since (opt-in)

Revision ID: c4e1a9f2b7d3
Revises: 75d3d5527a3e
Create Date: 2026-10-02 21:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4e1a9f2b7d3'
down_revision = '75d3d5527a3e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_alerts_since', sa.DateTime(timezone=True), nullable=True))


def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('email_alerts_since')
