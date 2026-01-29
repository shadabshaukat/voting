from sqlalchemy import text
from . import db


def run():
    """
    Idempotent schema migrations to keep older databases in sync with current models.
    - Adds polls.slug (and a unique index) if missing
    - Adds choices.is_correct (default false) if missing; backfills NULL to FALSE
    - Adds participants.company if missing
    """
    with db.engine.begin() as conn:
        # Polls: slug column + unique index (allows multiple NULLs)
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS slug VARCHAR(255);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_slug ON polls (slug);"))

        # Choices: is_correct, default false
        conn.execute(text("ALTER TABLE choices ADD COLUMN IF NOT EXISTS is_correct BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("UPDATE choices SET is_correct = FALSE WHERE is_correct IS NULL;"))

        # Participants: optional company field
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS company VARCHAR(150);"))


if __name__ == "__main__":
    run()
    print("Migrations applied successfully.")