from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from .. import models, schemas, db

router = APIRouter()


# ---------- Public Endpoints ----------
@router.get("/active", response_model=List[schemas.PollRead])
def get_active_polls(db_session: Session = Depends(db.get_db)):
    polls = db_session.query(models.Poll).filter(models.Poll.is_active == True).all()
    return polls


# Important: declare the static route before the dynamic one to avoid 422 due to path matching
@router.get("/by-title", response_model=schemas.PollRead)
def get_poll_by_title(title: str, db_session: Session = Depends(db.get_db)):
    poll = (
        db_session.query(models.Poll)
        .filter(
            models.Poll.is_active == True,
            func.lower(models.Poll.title) == func.lower(title),
        )
        .first()
    )
    if not poll:
        raise HTTPException(status_code=404, detail="Active poll not found for given title")
    return poll


@router.get("/{poll_id}", response_model=schemas.PollRead)
def get_poll(poll_id: int, db_session: Session = Depends(db.get_db)):
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id, models.Poll.is_active == True).first()
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
    poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id, models.Poll.is_active == True).first()
    if not poll:
        raise HTTPException(status_code=404, detail="Active poll not found")

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