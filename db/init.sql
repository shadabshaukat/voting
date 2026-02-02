-- DB-first schema initialization (PostgreSQL)
-- Creates the full application schema with IF NOT EXISTS, mirroring app/models.py
-- Safe to run multiple times.

BEGIN;

-- Users
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(150) NOT NULL UNIQUE,
    hashed_password TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT TRUE
);

-- Polls
CREATE TABLE IF NOT EXISTS polls (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    description TEXT NULL,
    slug VARCHAR(255) NULL,
    poll_type VARCHAR(20) NOT NULL DEFAULT 'trivia',
    is_active BOOLEAN DEFAULT FALSE,
    archived BOOLEAN DEFAULT FALSE,
    start_time TIMESTAMPTZ NULL,
    end_time TIMESTAMPTZ NULL,
    created_by INTEGER NULL REFERENCES users(id)
);

-- Ensure unique slug via index (allows NULLs and enforces uniqueness when present)
CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_slug ON polls (slug);

-- Questions
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES polls(id),
    text TEXT NOT NULL
);

-- Choices
CREATE TABLE IF NOT EXISTS choices (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    text VARCHAR(255) NOT NULL,
    is_correct BOOLEAN DEFAULT FALSE
);

-- Participants
CREATE TABLE IF NOT EXISTS participants (
    id SERIAL PRIMARY KEY,
    poll_id INTEGER NOT NULL REFERENCES polls(id),
    name VARCHAR(150) NOT NULL,
    company VARCHAR(150) NULL
);

-- Votes
CREATE TABLE IF NOT EXISTS votes (
    id SERIAL PRIMARY KEY,
    participant_id INTEGER NOT NULL REFERENCES participants(id),
    choice_id INTEGER NOT NULL REFERENCES choices(id),
    question_id INTEGER NOT NULL REFERENCES questions(id),
    timestamp TIMESTAMPTZ DEFAULT NOW()
);

-- Enforce a single vote per participant per question
CREATE UNIQUE INDEX IF NOT EXISTS uq_votes_participant_question ON votes (participant_id, question_id);

-- Helpful indexes for performance
CREATE INDEX IF NOT EXISTS ix_questions_poll_id ON questions(poll_id);
CREATE INDEX IF NOT EXISTS ix_choices_question_id ON choices(question_id);
CREATE INDEX IF NOT EXISTS ix_participants_poll_id ON participants(poll_id);
CREATE INDEX IF NOT EXISTS ix_votes_choice_id ON votes(choice_id);
CREATE INDEX IF NOT EXISTS ix_votes_participant_id ON votes(participant_id);
CREATE INDEX IF NOT EXISTS ix_votes_question_id ON votes(question_id);

COMMIT;

-- Note:
-- The application also runs idempotent startup migrations to backfill/ensure columns & indexes
-- if you are upgrading from older databases. With this DB-first script present, those migrations
-- will be effectively no-ops on a fresh database.