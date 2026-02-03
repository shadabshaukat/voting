from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timezone

from .. import models, schemas, db

router = APIRouter()


# ---------- Public Endpoints ----------
@router.get("/active", response_model=List[schemas.PollRead])
def get_active_polls(type: Optional[str] = None, db_session: Session = Depends(db.get_db)):
    q = db_session.query(models.Poll).filter(models.Poll.is_active == True, models.Poll.archived == False)
    if type:
        q = q.filter(func.lower(models.Poll.poll_type) == func.lower(type))
    return q.all()


# Important: declare the static route before the dynamic one to avoid 422 due to path matching
@router.get("/by-title", response_model=schemas.PollRead)
def get_poll_by_title(title: str, type: Optional[str] = None, db_session: Session = Depends(db.get_db)):
    q = (
        db_session.query(models.Poll)
        .filter(
            models.Poll.is_active == True,
            models.Poll.archived == False,
            func.lower(models.Poll.title) == func.lower(title),
        )
    )
    if type:
        q = q.filter(func.lower(models.Poll.poll_type) == func.lower(type))
    poll = q.first()
    if not poll:
        raise HTTPException(status_code=404, detail="Active poll not found for given title")
    return poll


@router.get("/by-slug", response_model=schemas.PollRead)
def get_poll_by_slug(slug: str, type: Optional[str] = None, db_session: Session = Depends(db.get_db)):
    q = db_session.query(models.Poll).filter(models.Poll.is_active == True, models.Poll.archived == False, func.lower(models.Poll.slug) == func.lower(slug))
    if type:
        q = q.filter(func.lower(models.Poll.poll_type) == func.lower(type))
    poll = q.first()
    if not poll:
        raise HTTPException(status_code=404, detail="Active poll not found for given slug")
    return poll

# Lightweight status endpoints to inform UI about closed/expired items
@router.get("/status/by-slug")
def get_status_by_slug(slug: str, db_session: Session = Depends(db.get_db)):
    poll = db_session.query(models.Poll).filter(func.lower(models.Poll.slug) == func.lower(slug)).first()
    if not poll:
        return {"exists": False}
    now = datetime.now(timezone.utc)
    expired = False
    try:
        if poll.end_time is not None:
            expired = (poll.end_time <= now)
    except Exception:
        expired = False
    return {
        "exists": True,
        "id": poll.id,
        "title": poll.title,
        "poll_type": getattr(poll, "poll_type", "trivia"),
        "is_active": bool(poll.is_active),
        "archived": bool(getattr(poll, "archived", False)),
        "expired": bool(expired),
    }

@router.get("/status/by-title")
def get_status_by_title(title: str, db_session: Session = Depends(db.get_db)):
    poll = (
        db_session.query(models.Poll)
        .filter(func.lower(models.Poll.title) == func.lower(title))
        .first()
    )
    if not poll:
        return {"exists": False}
    now = datetime.now(timezone.utc)
    expired = False
    try:
        if poll.end_time is not None:
            expired = (poll.end_time <= now)
    except Exception:
        expired = False
    return {
        "exists": True,
        "id": poll.id,
        "title": poll.title,
        "poll_type": getattr(poll, "poll_type", "trivia"),
        "is_active": bool(poll.is_active),
        "archived": bool(getattr(poll, "archived", False)),
        "expired": bool(expired),
    }


@router.get("/{poll_id}", response_model=schemas.PollRead)
def get_poll(poll_id: int, db_session: Session = Depends(db.get_db)):
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id, models.Poll.is_active == True, models.Poll.archived == False).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Active poll not found")
    return poll


# ---------- Vote Submission ----------
@router.post("/{poll_id}/submit", status_code=201)
def submit_votes(
    poll_id: int,
    vote_data: schemas.VoteSubmit,
    db_session: Session = Depends(db.get_db),
):
    poll = (
        db_session.query(models.Poll)
        .filter(
            models.Poll.id == poll_id,
            models.Poll.is_active == True,
            models.Poll.archived == False,
        )
        .first()
    )
    if not poll:
        raise HTTPException(status_code=404, detail="Active poll not found")

    # Enforce submission cutoff if end_time is set
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    try:
        if poll.end_time is not None:
            end = poll.end_time
            # ensure timezone-aware comparison
            if end.tzinfo is None:
                from datetime import timezone as _tz
                end = end.replace(tzinfo=_tz.utc)
            if now > end:
                raise HTTPException(status_code=403, detail="This session has ended. Submissions are closed.")
    except Exception:
        # if parsing fails, proceed without blocking
        pass

    # Create participant record
    participant = models.Participant(
        poll_id=poll.id, name=vote_data.participant.name, company=vote_data.participant.company
    )
    db_session.add(participant)
    db_session.flush()  # get participant.id

    # Validate and record each vote
    for vote in vote_data.votes:
        # Ensure question belongs to poll
        question = (
            db_session.query(models.Question)
            .filter(models.Question.id == vote.question_id, models.Question.poll_id == poll.id)
            .first()
        )
        if not question:
            raise HTTPException(status_code=400, detail=f"Invalid question ID {vote.question_id}")

        # Ensure choice belongs to question
        choice = (
            db_session.query(models.Choice)
            .filter(models.Choice.id == vote.choice_id, models.Choice.question_id == question.id)
            .first()
        )
        if not choice:
            raise HTTPException(status_code=400, detail=f"Invalid choice ID {vote.choice_id}")

        vote_record = models.Vote(participant_id=participant.id, choice_id=choice.id, question_id=question.id)
        db_session.add(vote_record)

    db_session.commit()
    return {"detail": "Votes submitted successfully"}