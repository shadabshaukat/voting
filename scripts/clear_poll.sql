-- Clear attendees (participants) and their votes for a specific poll.
-- This resets leaderboard/winners/results without touching users, polls, questions, or choices.

-- Option A: run by poll_id (psql style)
-- Usage in psql: \set poll_id 42
-- Then: \i scripts/clear_poll.sql

BEGIN;

-- Delete votes tied to participants of this poll
DELETE FROM votes
WHERE participant_id IN (
  SELECT id FROM participants WHERE poll_id = :poll_id
);

-- Defensive: also delete any votes through choices for this poll
DELETE FROM votes v
USING choices c, questions q
WHERE v.choice_id = c.id
  AND c.question_id = q.id
  AND q.poll_id = :poll_id;

-- Delete participants of this poll
DELETE FROM participants
WHERE poll_id = :poll_id;

COMMIT;


-- Option B: run by slug (replace your-code-here)
-- BEGIN;
-- WITH pid AS (
--   SELECT id FROM polls WHERE lower(slug) = lower($$your-code-here$$)
-- )
-- DELETE FROM votes
-- WHERE participant_id IN (
--   SELECT id FROM participants WHERE poll_id IN (SELECT id FROM pid)
-- );
-- DELETE FROM votes v
-- USING choices c, questions q
-- WHERE v.choice_id = c.id
--   AND c.question_id = q.id
--   AND q.poll_id IN (SELECT id FROM pid);
-- DELETE FROM participants
-- WHERE poll_id IN (SELECT id FROM pid);
-- COMMIT;


-- Optional sanity checks (run before/after):
-- SELECT COUNT(*) AS participants FROM participants WHERE poll_id = :poll_id;
-- SELECT COUNT(*) AS votes
-- FROM votes v
-- JOIN participants p ON p.id = v.participant_id
-- WHERE p.poll_id = :poll_id;
