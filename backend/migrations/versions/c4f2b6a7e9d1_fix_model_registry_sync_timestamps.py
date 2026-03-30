"""fix model registry sync timestamps

Revision ID: c4f2b6a7e9d1
Revises: a5f0c9b3d1e2
Create Date: 2026-03-21 19:15:00.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "c4f2b6a7e9d1"
down_revision = "a5f0c9b3d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'model_providers'
                  AND column_name = 'last_synced_at'
                  AND data_type = 'timestamp without time zone'
            ) THEN
                ALTER TABLE model_providers
                ALTER COLUMN last_synced_at TYPE TIMESTAMP WITH TIME ZONE
                USING last_synced_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'models'
                  AND column_name = 'last_synced_at'
                  AND data_type = 'timestamp without time zone'
            ) THEN
                ALTER TABLE models
                ALTER COLUMN last_synced_at TYPE TIMESTAMP WITH TIME ZONE
                USING last_synced_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'models'
                  AND column_name = 'last_synced_at'
                  AND data_type = 'timestamp with time zone'
            ) THEN
                ALTER TABLE models
                ALTER COLUMN last_synced_at TYPE TIMESTAMP WITHOUT TIME ZONE
                USING last_synced_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'model_providers'
                  AND column_name = 'last_synced_at'
                  AND data_type = 'timestamp with time zone'
            ) THEN
                ALTER TABLE model_providers
                ALTER COLUMN last_synced_at TYPE TIMESTAMP WITHOUT TIME ZONE
                USING last_synced_at AT TIME ZONE 'UTC';
            END IF;
        END $$;
        """
    )
