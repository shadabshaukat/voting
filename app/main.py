import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from . import db, models, auth
from .routers import admin, poll
from sqlalchemy import text

app = FastAPI(
    title="Voting & Trivia Application",
    description="API for creating polls/trivia, collecting votes, and viewing results.",
    version="0.1.0",
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")
# Allow frontend (served from same origin or any for dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
# Root endpoint  serve the attendee UI (index.html)
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# Admin dashboard  serve the admin UI (admin.html)
@app.get("/admin", response_class=HTMLResponse)
async def admin_root(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(poll.router, prefix="/poll", tags=["poll"])

# Lightweight, idempotent migrations to keep DB schema in sync when columns are added later
# This avoids 500s like "column polls.slug does not exist" on older databases

def run_startup_migrations():
    with db.engine.begin() as conn:
        # Add missing columns if the DB was created before these fields existed
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS slug VARCHAR(255);"))
        # Create a unique index for slug to mimic uniqueness (portable and safe)
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_polls_slug ON polls (slug);"))

        conn.execute(text("ALTER TABLE choices ADD COLUMN IF NOT EXISTS is_correct BOOLEAN DEFAULT FALSE;"))
        conn.execute(text("UPDATE choices SET is_correct = FALSE WHERE is_correct IS NULL;"))

        # In case participants.company/full_name/email were added later
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS company VARCHAR(150);"))
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS full_name VARCHAR(150);"))
        conn.execute(text("UPDATE participants SET full_name = name WHERE full_name IS NULL AND name IS NOT NULL;"))
        conn.execute(text("ALTER TABLE participants ADD COLUMN IF NOT EXISTS email VARCHAR(255);"))

        # Poll type column for different modes: 'trivia' (has correct answers) vs 'survey'/'poll'
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS poll_type VARCHAR(20) DEFAULT 'trivia';"))
        # Archived flag to preserve analytics but hide from attendee selection
        conn.execute(text("ALTER TABLE polls ADD COLUMN IF NOT EXISTS archived BOOLEAN DEFAULT FALSE;"))

        # Votes: ensure question_id exists and is backfilled; add unique index to prevent duplicate votes per question
        conn.execute(text("ALTER TABLE votes ADD COLUMN IF NOT EXISTS question_id INTEGER;"))
        conn.execute(text(
            """
            UPDATE votes v
            SET question_id = c.question_id
            FROM choices c
            WHERE v.choice_id = c.id AND v.question_id IS NULL;
            """
        ))
        conn.execute(text("ALTER TABLE votes ALTER COLUMN question_id SET NOT NULL;"))
        conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS uq_votes_participant_question ON votes (participant_id, question_id);"))

# Create DB tables on startup if they don't exist
@app.on_event("startup")
def on_startup():
    # Create tables
    models.Base.metadata.create_all(bind=db.engine)

    # Apply idempotent migrations for older databases
    run_startup_migrations()

    # Ensure a default admin user exists
    db_session = db.SessionLocal()
    try:
        admin_exists = db_session.query(models.User).filter(models.User.is_admin == True).first()
        if not admin_exists:
            default_admin = models.User(
                username="admin",
                hashed_password=auth.get_password_hash("admin123"),
                is_admin=True,
            )
            db_session.add(default_admin)
            db_session.commit()
    finally:
        db_session.close()
if __name__ == "__main__":
    import os
    host = os.getenv("UVICORN_HOST", "0.0.0.0")
    http_port = int(os.getenv("UVICORN_PORT", "8000"))
    enable_https = os.getenv("ENABLE_HTTPS", "false").lower() in ("1","true","yes")
    ssl_certfile = os.getenv("SSL_CERTFILE")
    ssl_keyfile = os.getenv("SSL_KEYFILE")
    https_port = int(os.getenv("HTTPS_PORT", "443"))
    if enable_https and ssl_certfile and ssl_keyfile:
        uvicorn.run("app.main:app", host=host, port=https_port, reload=True, ssl_certfile=ssl_certfile, ssl_keyfile=ssl_keyfile)
    else:
        uvicorn.run("app.main:app", host=host, port=http_port, reload=True)