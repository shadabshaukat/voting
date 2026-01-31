from sqlalchemy import text
from . import db


def run():
    """
    Idempotent schema migrations to keep older databases in sync with current models.
    - Adds polls.slug (and a unique index) if missing
    - Adds choices.is_correct (default false) if missing; backfills NULL to FALSE
    - Adds participants.company if missing
    - Adds participants.full_name and participants.email if missing (backfill full_name from legacy name)
    - Adds votes.question_id (backfilled from choices) and unique index on (participant_id, question_id)
    - Adds polls.poll_type with default 'trivia'
    - Adds polls.archived (default false)
    """
    with db.engine.begin() as conn:
        # Polls: slug column + unique index (allows multiple NULLs)
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS slug VARCHAR(255);"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_slug ON polls (slug);"))

        # Choices: is_correct, default false (used by trivia type)
        conn.execute(text("ALTER TABLE choices ADD COLUMN IF NOT EXISTS is_correct BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("UPDATE choices SET is_correct = FALSE WHERE is_correct IS NULL;"))

        # Participants: add fields (company, full_name, email)
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS company VARCHAR(150);"))
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS full_name VARCHAR(150);"))
        conn.execute(text("UPDATE participants SET full_name = name WHERE full_name IS NULL AND name IS NOT NULL;"))
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS email VARCHAR(255);"))

        # Poll type: supports 'trivia' (has correct answers) and 'survey'/'poll' (no correct answers)
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS poll_type VARCHAR(20) DEFAULT 'trivia';"))
        # Archive flag to keep historical analytics while hiding from active selection
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE;"))

        # Votes: add question_id, backfill from choices, set NOT NULL, and enforce uniqueness per participant/question
        conn.execute(text("ALTER TABLE votes ADD COLUMN IF NOT EXISTS question_id INTEGER;"))
        # Backfill question_id using choice -> question mapping
        conn.execute(text(
            """
            UPDATE votes v
            SET question_id = c.question_id
            FROM choices c
            WHERE v.choice_id = c.id AND v.question_id IS NULL;
            """
        ))
        # Ensure NOT NULL after backfill
        conn.execute(text("ALTER TABLE votes ALTER COLUMN question_id SET NOT NULL;"))
        # Unique constraint to prevent duplicate votes per participant/question
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_votes_participant_question ON votes (participant_id, question_id);"))


if __name__ == "__main__":
    run()
    print("Migrations applied successfully.")