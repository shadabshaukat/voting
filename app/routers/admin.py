from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas, db, auth, config

router = APIRouter()


# ---------- Simple JSON Authentication ----------
class LoginRequest(BaseModel):
    username: str
    password: str

@router.post("/login", response_model=schemas.Token)
def login(login_req: LoginRequest):
    # Simple validation against credentials stored in .env via Settings
    if (
        login_req.username != config.settings.ADMIN_USERNAME
        or login_req.password != config.settings.ADMIN_PASSWORD
    ):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    # If credentials match, generate a token for the admin user
    access_token = auth.create_access_token(data={"sub": login_req.username})
    return {"access_token": access_token, "token_type": "bearer"}


# ---------- Admin User Creation (initial setup) ----------
@router.post("/create-admin", response_model=schemas.Token)
def create_admin(
    user_in: schemas.UserCreate,
    db_session: Session = Depends(db.SessionLocal),
):
    existing = db_session.query(models.User).filter(models.User.username == user_in.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
    hashed_password = auth.get_password_hash(user_in.password)
    admin_user = models.User(username=user_in.username, hashed_password=hashed_password, is_admin=True)
    db_session.add(admin_user)
    db_session.commit()
    db_session.refresh(admin_user)
    access_token = auth.create_access_token(data={"sub": admin_user.username})
    return {"access_token": access_token, "token_type": "bearer"}


# ---------- Poll Management ----------
@router.post("/polls", response_model=schemas.PollRead)
def create_poll(poll_in: schemas.PollCreate, db_session: Session = Depends(db.SessionLocal)):
    # Create Poll
    poll = models.Poll(
        title=poll_in.title,
        description=poll_in.description,
        is_active=False,
        start_time=poll_in.start_time,
        end_time=poll_in.end_time,
        created_by=db_session.query(models.User).filter(models.User.is_admin == True).first().id,
    )
    db_session.add(poll)
    db_session.flush()  # get poll.id

    # Create Questions and Choices
    for q in poll_in.questions:
        question = models.Question(poll_id=poll.id, text=q.text)
        db_session.add(question)
        db_session.flush()
        for c in q.choices:
            choice = models.Choice(question_id=question.id, text=c.text)
            db_session.add(choice)

    db_session.commit()
    db_session.refresh(poll)
    return poll


@router.get("/polls", response_model=List[schemas.PollRead])
def list_polls(db_session: Session = Depends(db.SessionLocal)):
    polls = db_session.query(models.Poll).all()
    return polls


@router.get("/polls/{poll_id}", response_model=schemas.PollRead, dependencies=[Depends(auth.get_current_admin_user)])
def get_poll(poll_id: int, db_session: Session = Depends(db.SessionLocal)):
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    return poll


@router.post("/polls/{poll_id}/activate", dependencies=[Depends(auth.get_current_admin_user)])
def activate_poll(poll_id: int, db_session: Session = Depends(db.SessionLocal)):
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    poll.is_active = True
    poll.start_time = datetime.utcnow()
    db_session.commit()
    return {"detail": "Poll activated"}


@router.post("/polls/{poll_id}/deactivate", dependencies=[Depends(auth.get_current_admin_user)])
def deactivate_poll(poll_id: int, db_session: Session = Depends(db.SessionLocal)):
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")
    poll.is_active = False
    poll.end_time = datetime.utcnow()
    db_session.commit()
    return {"detail": "Poll deactivated"}


# ---------- Results ----------
@router.get("/polls/{poll_id}/results", dependencies=[Depends(auth.get_current_admin_user)])
def poll_results(poll_id: int, db_session: Session = Depends(db.SessionLocal)):
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Poll not found")

    results = []
    for question in poll.questions:
        q_res = {"question_id": question.id, "question_text": question.text, "choices": []}
        for choice in question.choices:
            vote_count = db_session.query(models.Vote).filter(models.Vote.choice_id == choice.id).count()
            q_res["choices"].append({"choice_id": choice.id, "choice_text": choice.text, "votes": vote_count})
        results.append(q_res)

    return {"poll_id": poll.id, "title": poll.title, "results": results}