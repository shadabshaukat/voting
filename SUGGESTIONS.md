# Voting App: Architecture Summary and Recommendations

## Current Architecture (quick read)
- Stack: FastAPI (sync SQLAlchemy + psycopg2), server-rendered HTML templates (Jinja for admin/attendee shells), vanilla JS, Chart.js for results, service worker scaffolding present.
- Data model: users (admin), polls, questions, choices, participants, votes. `votes` has unique index on (participant_id, question_id) to prevent duplicate answers per participant/question.
- Admin: JSON login to get JWT; CRUD-like actions (create poll, activate/deactivate/reactivate, delete, export CSV, results, leaderboard, winners).
- Attendee: join via type + title/slug or active session; enter name/company; fetch poll; submit votes.
- Migrations: lightweight idempotent startup SQL ensures columns and unique index.

## Changes implemented (this PR)
- Attendee timer: simplified to "Time Remaining: mm:ss" (accessible, tabular numbers, auto-submit on zero).
- Admin events list: per-row collapsible body with all actions + per-row details and inline results panel. Tidy, minimal controls with a single expand toggle.
- UI/UX alignment cleanup: option labels rendered on a single visual line with wrapping next to the radio checkbox; consistent row action spacing; subtle timer pill.
- Admin security hardening: all /admin/polls* and analytics endpoints now require a valid admin JWT (auth header). Login ensures a DB admin user exists for token resolution.
- CSV download now includes Authorization header for protected export.

## Targeted UI/UX recommendations
- Attendee
  - Move inline modal styles to CSS classes for a fully consistent theme.
  - Add progress marker (e.g., "Question 2/5") and optional per-question timer for trivia.
  - Provide immediate form validation hints (required choice) and "Change answer" affordance before submit.
- Admin
  - Add filters (type/active/expired) and a quick search box for Events list.
  - Add bulk actions (archive/delete) and confirm dialogs with clear copy.
  - Replace prompt() for Reactivate with a compact inline input + Apply button.
  - Add pagination when events > 25; keep top N active/most recent pinned.
  - Persist expand/collapse state per row across reloads (localStorage key on poll id).

## Accessibility (A11y)
- Ensure all buttons have discernible text; add aria labels on icon-only controls (row toggle done).
- Maintain focus states, keyboard navigation for expanding rows, results panel, and modal forms.
- aria-live polite region used for the timer; extend to status chips (Active/Inactive/Expired) on updates.

## Stability, performance, and scalability
- Database
  - Indexes (if missing in the DB):
    - questions.poll_id, choices.question_id, participants.poll_id, votes.choice_id, votes.participant_id, votes.question_id (already has unique composite).
  - Query optimization for results/CSV:
    - Replace per-choice COUNT(*) in loops with a single GROUP BY for a question:
      ```sql
      SELECT c.id, c.text, c.is_correct, COUNT(v.id) AS votes
      FROM choices c
      LEFT JOIN votes v ON v.choice_id = c.id
      WHERE c.question_id = :qid
      GROUP BY c.id, c.text, c.is_correct
      ```
    - In FastAPI, fetch all questions for a poll and run one query per question rather than per-choice loops.
  - Consider a lightweight materialized counter table (choice_vote_counts) updated by triggers for real‑time dashboards at scale.

- Concurrency & throughput
  - Run behind a process manager with multiple workers (e.g., gunicorn with uvicorn workers). Add PgBouncer for connection pooling.
  - Use async stack (async SQLAlchemy + asyncpg) if moving toward very high concurrency; or keep sync but increase workers and rely on pooling.
  - Rate-limit vote submissions by IP + user agent + optional signed client token to reduce abuse during public sessions (Redis-based leaky bucket).
  - Idempotency keys: generate a per-session id and refuse a second submission for the same poll if business rules require single submission per attendee.

- Caching / real-time
  - Push live updates (SSE or WebSocket) to admin results to avoid polling and to scale cleanly.
  - Cache read endpoints with short TTL (e.g., /poll/{id}) via reverse proxy (Cloudflare/NGINX) when acceptable.

- Reliability & data integrity
  - Use transactions with proper isolation for submission; already covered implicitly by session commit, but wrap the participant+votes creation in a single transaction context to ensure atomicity.
  - Enforce cascading deletes at DB level (FK ON DELETE CASCADE) to simplify manual cleanup logic.

- Security
  - Move ADMIN_USERNAME/ADMIN_PASSWORD out of static .env for production. Integrate a proper admin user store with password rotation, and 2FA if needed.
  - Tighten CORS in production (allow specific admin origin, not "*").
  - Consider CSRF protection if you ever serve admin from a browser with cookie-based auth; current JWT header model is fine.

## Product features to consider
- Multi-question types: free text, multi-select, ranking, NPS-style scales (1–10), rating stars.
- Scheduling: auto-activate/deactivate on start/end times, with timezone support.
- Session management: cap per-company submissions, throttle one submission per user email/phone (if you later collect that), and optional OTP for closed events.
- Advanced analytics: per-question heatmaps, export per-participant CSV, anonymized aggregates, and downloadable PDF summary.
- Theming: lightweight theme variables (CSS custom properties) to custom brand per event.

## Ops and observability
- Add structured logging (uvicorn + loguru) with request IDs. Export logs to CloudWatch/ELK.
- Metrics: Prometheus endpoint (latency, QPS, DB usage, votes/sec, errors).
- Health checks and readiness endpoints for container orchestration.

## Migration improvements (optional)
- Extend `run_startup_migrations()` to add the recommended indexes if they’re missing:
  ```sql
  CREATE INDEX IF NOT EXISTS ix_questions_poll_id ON questions(poll_id);
  CREATE INDEX IF NOT EXISTS ix_choices_question_id ON choices(question_id);
  CREATE INDEX IF NOT EXISTS ix_participants_poll_id ON participants(poll_id);
  CREATE INDEX IF NOT EXISTS ix_votes_choice_id ON votes(choice_id);
  CREATE INDEX IF NOT EXISTS ix_votes_participant_id ON votes(participant_id);
  ```
- Consider a background job to backfill counts into a denormalized table if you adopt counters.

## Next steps I can implement quickly
- Real-time admin results via SSE (server-sent events) to remove clicks and polling.
- GROUP BY optimization in results and CSV endpoints.
- Filters/search/pagination for the admin Events list.
- Theme tokens and extracting inline styles to CSS for fully uniform minimalism.