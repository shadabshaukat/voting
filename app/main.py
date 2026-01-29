import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

from . import db, models, auth
from .routers import admin, poll

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
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(poll.router, prefix="/poll", tags=["poll"])

# Create DB tables on startup if they don't exist
@app.on_event("startup")
def on_startup():
    # Create tables
    models.Base.metadata.create_all(bind=db.engine)

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
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)