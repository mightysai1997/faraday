"""cvss_model

Revision ID: d8f0b32a5c0e
Revises: f28eae25416b
Create Date: 2021-09-01 10:30:06.693843+00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd8f0b32a5c0e'
down_revision = 'f28eae25416b'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('cvss_base',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('version', sa.String(length=8), nullable=False),
                    sa.Column('vector_string', sa.String(length=64)),
                    sa.Column('type', sa.String(length=24), nullable=True),
                    sa.Column('base_score', sa.Float(), default=0.0),
                    sa.Column('fixed_base_score', sa.Float(), default=0.0),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('cvss_v2',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('access_vector', sa.Enum('N', 'A', 'L', name='cvss_access_vector')),
                    sa.Column('access_complexity', sa.Enum('L', 'M', 'H', name='cvss_access_complexity')),
                    sa.Column('authentication', sa.Enum('N', 'S', 'M', name='cvss_authentication')),
                    sa.Column('confidentiality_impact', sa.Enum('N', 'P', 'C', name='cvss_impact_types_v2')),
                    sa.Column('integrity_impact', sa.Enum('N', 'P', 'C', name='cvss_impact_types_v2')),
                    sa.Column('availability_impact', sa.Enum('N', 'P', 'C', name='cvss_impact_types_v2')),
                    sa.ForeignKeyConstraint(['id'], ['cvss_base.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )
    op.create_table('cvss_v3',
                    sa.Column('id', sa.Integer(), nullable=False),
                    sa.Column('attack_vector', sa.Enum('N', 'A', 'L', 'P', name='cvss_attack_vector')),
                    sa.Column('attack_complexity', sa.Enum('L', 'H', name='cvss_attack_complexity')),
                    sa.Column('privileges_required', sa.Enum('N', 'L', 'H', name='cvss_privileges_required')),
                    sa.Column('user_interaction', sa.Enum('N', 'R', name='cvss_user_interaction')),
                    sa.Column('scope', sa.Enum('U', 'C', name='cvss_scope')),
                    sa.Column('confidentiality_impact', sa.Enum('N', 'L', 'H', name='cvss_impact_types_v3')),
                    sa.Column('integrity_impact', sa.Enum('N', 'L', 'H', name='cvss_impact_types_v3')),
                    sa.Column('availability_impact', sa.Enum('N', 'L', 'H', name='cvss_impact_types_v3')),
                    sa.ForeignKeyConstraint(['id'], ['cvss_base.id'], ),
                    sa.PrimaryKeyConstraint('id')
                    )

    # Vuln relationship with cvss
    op.add_column('vulnerability', sa.Column('cvssv2_id', sa.Integer(), nullable=True))
    op.add_column('vulnerability', sa.Column('cvssv3_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'vulnerability', 'cvss_v2', ['cvssv2_id'], ['id'])
    op.create_foreign_key(None, 'vulnerability', 'cvss_v3', ['cvssv3_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # op.drop_constraint(None, 'vulnerability', type_='foreignkey')
    op.drop_column('vulnerability', 'cvssv2_id')
    op.drop_column('vulnerability', 'cvssv3_id')
    op.drop_table('cvss_v3')
    op.drop_table('cvss_v2')
    op.drop_table('cvss_base')
    op.execute('drop type cvss_attack_complexity')
    op.execute('drop type cvss_access_vector')
    op.execute('drop type cvss_access_complexity')
    op.execute('drop type cvss_attack_vector')
    op.execute('drop type cvss_authentication')
    op.execute('drop type cvss_privileges_required')
    op.execute('drop type cvss_scope')
    op.execute('drop type cvss_user_interaction')
    op.execute('drop type cvss_impact_types_v2')
    op.execute('drop type cvss_impact_types_v3')
    #
    # ### end Alembic commands ###
