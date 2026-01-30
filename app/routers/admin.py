from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
import random
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, schemas, db, auth, config

router = APIRouter()

# Manual serializer to avoid Pydantic for responses

def serialize_poll(poll: models.Poll) -> dict:
    return {
        "id": poll.id,
        "title": poll.title,
        "description": poll.description,
        "slug": poll.slug,
        "poll_type": getattr(poll, "poll_type", "trivia"),
        "is_active": bool(poll.is_active),
        "start_time": poll.start_time.isoformat() if poll.start_time else None,
        "end_time": poll.end_time.isoformat() if poll.end_time else None,
        "questions": [
            {
                "id": q.id,
                "text": q.text,
                "choices": [
                    {"id": c.id, "text": c.text, "is_correct": bool(getattr(c, "is_correct", False))}
                    for c in q.choices
                ],
            }
            for q in poll.questions
        ],
    }


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
    db_session: Session = Depends(db.get_db),
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
@router.post("/polls")
async def create_poll(request: Request):
    db_session = db.SessionLocal()
    try:
        payload = await request.json()

        title = (payload.get("title") or "").strip()
        description = payload.get("description")
        poll_type = (payload.get("poll_type") or "trivia").strip().lower()
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        questions = payload.get("questions", [])

        if not title:
            raise HTTPException(status_code=400, detail="Title is required")

        admin_user = db_session.query(models.User).filter(models.User.is_admin == True).first()
        created_by = admin_user.id if admin_user else 0

        # Parse datetimes if provided (ISO strings)
        from datetime import datetime
        def parse_dt(v):
            if not v:
                return None
            try:
                return datetime.fromisoformat(v.replace("Z", "+00:00"))
            except Exception:
                return None

        # Generate slug from title and ensure uniqueness
        import re
        base_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
        slug = base_slug or f"poll-{int(datetime.utcnow().timestamp())}"
        i = 2
        while db_session.query(models.Poll).filter(models.Poll.slug == slug).first():
            slug = f"{base_slug}-{i}"
            i += 1

        poll = models.Poll(
            title=title,
            description=description,
            slug=slug,
            poll_type=poll_type,
            is_active=False,
            start_time=parse_dt(start_time),
            end_time=parse_dt(end_time),
            created_by=created_by,
        )
        db_session.add(poll)
        db_session.flush()

        for q in questions:
            q_text = (q.get("text") or "").strip()
            if not q_text:
                continue
            question = models.Question(poll_id=poll.id, text=q_text)
            db_session.add(question)
            db_session.flush()
            for c in q.get("choices", []):
                c_text = (c.get("text") or "").strip()
                if not c_text:
                    continue
                is_correct = bool(c.get("is_correct", False)) if poll_type in ("trivia", "poll") else False
                choice = models.Choice(question_id=question.id, text=c_text, is_correct=is_correct)
                db_session.add(choice)

        db_session.commit()
        db_session.refresh(poll)
        return serialize_poll(poll)
    finally:
        db_session.close()


@router.delete("/polls/{poll_id}")
def delete_poll(poll_id: int):
    """Delete a poll and all related data (questions, choices, participants, votes).
    Cascades are configured on relationships, so ORM delete will remove dependents."""
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        db_session.delete(poll)
        db_session.commit()
        return {"detail": "Poll deleted"}
    finally:
        db_session.close()


@router.get("/polls")
def list_polls():
    db_session = db.SessionLocal()
    try:
        polls = db_session.query(models.Poll).all()
        return [serialize_poll(p) for p in polls]
    finally:
        db_session.close()


@router.get("/polls/{poll_id}")
def get_poll(poll_id: int):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        return serialize_poll(poll)
    finally:
        db_session.close()


@router.post("/polls/{poll_id}/activate")
def activate_poll(poll_id: int):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        poll.is_active = True
        poll.start_time = datetime.utcnow()
        db_session.commit()
        return {"detail": "Poll activated"}
    finally:
        db_session.close()


@router.post("/polls/{poll_id}/deactivate")
def deactivate_poll(poll_id: int):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        poll.is_active = False
        poll.end_time = datetime.utcnow()
        db_session.commit()
        return {"detail": "Poll deactivated"}
    finally:
        db_session.close()


# ---------- Results ----------
@router.get("/polls/{poll_id}/results")
def poll_results(poll_id: int):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")

        results = []
        for question in poll.questions:
            q_res = {"question_id": question.id, "question_text": question.text, "choices": []}
            for choice in question.choices:
                vote_count = db_session.query(models.Vote).filter(models.Vote.choice_id == choice.id).count()
                q_res["choices"].append({
                    "choice_id": choice.id,
                    "choice_text": choice.text,
                    "votes": vote_count,
                    "is_correct": bool(getattr(choice, "is_correct", False))
                })
            results.append(q_res)

        return {"poll_id": poll.id, "title": poll.title, "poll_type": getattr(poll, "poll_type", "trivia"), "results": results}
    finally:
        db_session.close()


@router.get("/polls/{poll_id}/winners")
def poll_winners(poll_id: int):
    """Compute winners (participants with all answers correct). Only valid for 'trivia' polls."""
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        if getattr(poll, "poll_type", "trivia") != "trivia":
            raise HTTPException(status_code=400, detail="Winners are only applicable for trivia polls")
        total_questions = len(poll.questions)
        correct_choice_ids = set(
            c.id for q in poll.questions for c in q.choices if getattr(c, "is_correct", False)
        )
        participants = db_session.query(models.Participant).filter(models.Participant.poll_id == poll_id).all()
        results = []
        for p in participants:
            votes = db_session.query(models.Vote).filter(models.Vote.participant_id == p.id).all()
            correct = sum(1 for v in votes if v.choice_id in correct_choice_ids)
            results.append({
                "participant_id": p.id,
                "name": p.name,
                "company": p.company,
                "correct_count": correct,
                "total_questions": total_questions,
                "is_winner": (correct == total_questions and total_questions > 0)
            })
        winners = [r for r in results if r["is_winner"]]
        return {"poll_id": poll.id, "title": poll.title, "total_questions": total_questions, "participants": results, "winners": winners}
    finally:
        db_session.close()


@router.post("/polls/{poll_id}/pick-winner")
def pick_random_winner(poll_id: int):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        if getattr(poll, "poll_type", "trivia") != "trivia":
            raise HTTPException(status_code=400, detail="Picking a winner is only applicable for trivia polls")
        total_questions = len(poll.questions)
        correct_choice_ids = set(
            c.id for q in poll.questions for c in q.choices if getattr(c, "is_correct", False)
        )
        participants = db_session.query(models.Participant).filter(models.Participant.poll_id == poll_id).all()
        winners = []
        for p in participants:
            votes = db_session.query(models.Vote).filter(models.Vote.participant_id == p.id).all()
            correct = sum(1 for v in votes if v.choice_id in correct_choice_ids)
            if correct == total_questions and total_questions > 0:
                winners.append({"participant_id": p.id, "name": p.name, "company": p.company})
        if not winners:
            raise HTTPException(status_code=400, detail="No winners found")
        selected = random.choice(winners)
        return {"winner": selected, "count": len(winners)}
    finally:
        db_session.close()