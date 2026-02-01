from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request, Response
import random
import io, csv
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from .. import models, schemas, db, auth, config

router = APIRouter()

# Manual serializer to avoid Pydantic for responses

def serialize_poll(poll: models.Poll) -> dict:
    now = datetime.now(timezone.utc)
    expired = False
    try:
        if poll.end_time is not None:
            expired = (poll.end_time <= now)
    except Exception:
        expired = False
    return {
        "id": poll.id,
        "title": poll.title,
        "description": poll.description,
        "slug": poll.slug,
        "poll_type": getattr(poll, "poll_type", "trivia"),
        "is_active": bool(poll.is_active),
        "archived": bool(getattr(poll, "archived", False)),
        "expired": bool(expired),
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
def login(login_req: LoginRequest, db_session: Session = Depends(db.get_db)):
    # Validate against credentials stored in .env via Settings
    if (
        login_req.username != config.settings.ADMIN_USERNAME
        or login_req.password != config.settings.ADMIN_PASSWORD
    ):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    # Ensure a corresponding admin user exists in DB for token validation on protected endpoints
    user = db_session.query(models.User).filter(models.User.username == login_req.username).first()
    if not user:
        user = models.User(
            username=login_req.username,
            hashed_password=auth.get_password_hash(login_req.password),
            is_admin=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    elif not user.is_admin:
        user.is_admin = True
        db_session.commit()
    access_token = auth.create_access_token(data={"sub": user.username})
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
async def create_poll(request: Request, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        payload = await request.json()

        title = (payload.get("title") or "").strip()
        description = payload.get("description")
        poll_type = (payload.get("poll_type") or "trivia").strip().lower()
        start_time = payload.get("start_time")
        end_time = payload.get("end_time")
        questions = payload.get("questions", [])
        requested_slug = (payload.get("slug") or "").strip().lower() or None

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

        # Generate or validate slug (supports custom short code)
        import re, random, string
        def unique_slug(base: str) -> str:
            s = base or f"poll-{int(datetime.utcnow().timestamp())}"
            i = 2
            while db_session.query(models.Poll).filter(models.Poll.slug == s).first():
                s = f"{base}-{i}"
                i += 1
            return s

        if requested_slug:
            base_slug = re.sub(r"[^a-z0-9]+", "-", requested_slug.lower()).strip("-")
            base_slug = base_slug or ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
            slug = unique_slug(base_slug)
        else:
            base_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            slug = unique_slug(base_slug)

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
def delete_poll(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
    """Robustly delete a poll and all related data via SQL (votes -> participants/choices -> questions -> poll)."""
    db_session = db.SessionLocal()
    try:
        exists = db_session.query(models.Poll.id).filter(models.Poll.id == poll_id).first()
        if not exists:
            raise HTTPException(status_code=404, detail="Poll not found")
        with db.engine.begin() as conn:
            # Delete votes linked via participants for this poll
            conn.execute(text(
                """
                DELETE FROM votes
                WHERE participant_id IN (
                    SELECT id FROM participants WHERE poll_id = :pid
                )
                """
            ), {"pid": poll_id})
            # Delete votes linked via choices for this poll
            conn.execute(text(
                """
                DELETE FROM votes v
                USING choices c, questions q
                WHERE v.choice_id = c.id AND c.question_id = q.id AND q.poll_id = :pid
                """
            ), {"pid": poll_id})
            # Delete participants for this poll
            conn.execute(text("DELETE FROM participants WHERE poll_id = :pid"), {"pid": poll_id})
            # Delete choices for this poll (via questions)
            conn.execute(text(
                """
                DELETE FROM choices
                WHERE question_id IN (SELECT id FROM questions WHERE poll_id = :pid)
                """
            ), {"pid": poll_id})
            # Delete questions for this poll
            conn.execute(text("DELETE FROM questions WHERE poll_id = :pid"), {"pid": poll_id})
            # Finally delete the poll
            conn.execute(text("DELETE FROM polls WHERE id = :pid"), {"pid": poll_id})
        return {"detail": "Poll deleted"}
    finally:
        db_session.close()


@router.get("/polls")
def list_polls(_: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        polls = db_session.query(models.Poll).all()
        return [serialize_poll(p) for p in polls]
    finally:
        db_session.close()


@router.get("/polls/{poll_id}")
def get_poll(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        return serialize_poll(poll)
    finally:
        db_session.close()


@router.post("/polls/{poll_id}/activate")
def activate_poll(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
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
def deactivate_poll(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
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


# ---------- Reactivate with duration ----------
class ReactivateRequest(BaseModel):
    minutes: int = 2

@router.post("/polls/{poll_id}/reactivate")
def reactivate_poll(poll_id: int, req: ReactivateRequest, _: models.User = Depends(auth.get_current_admin_user)):
    """
    Reactivate a poll for the given duration (minutes) and CLEAR any previous attendee
    submissions so the event restarts fresh.

    Clearing entails removing all votes for this poll and all its participants, while
    keeping the poll, questions, and choices intact.
    """
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        # Clamp minutes to at least 1
        minutes = 1
        try:
            minutes = max(1, int(getattr(req, 'minutes', 2) or 2))
        except Exception:
            minutes = 2

        # Purge previous attendees and votes so leaderboard/results reset
        with db.engine.begin() as conn:
            # Delete votes linked via participants for this poll
            conn.execute(text(
                """
                DELETE FROM votes
                WHERE participant_id IN (
                    SELECT id FROM participants WHERE poll_id = :pid
                )
                """
            ), {"pid": poll_id})
            # Also delete any votes joined through choices for this poll (safety)
            conn.execute(text(
                """
                DELETE FROM votes v
                USING choices c, questions q
                WHERE v.choice_id = c.id AND c.question_id = q.id AND q.poll_id = :pid
                """
            ), {"pid": poll_id})
            # Finally delete participants for this poll
            conn.execute(text("DELETE FROM participants WHERE poll_id = :pid"), {"pid": poll_id})

        # Activate with new time window
        now = datetime.utcnow()
        from datetime import timedelta
        poll.is_active = True
        poll.archived = False
        poll.start_time = now
        poll.end_time = now + timedelta(minutes=minutes)
        db_session.commit()
        db_session.refresh(poll)
        return serialize_poll(poll)
    finally:
        db_session.close()

@router.post("/polls/{poll_id}/archive")
def archive_poll(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        poll.archived = True
        poll.is_active = False
        if not poll.end_time:
            poll.end_time = datetime.utcnow()
        db_session.commit()
        return {"detail": "Poll archived"}
    finally:
        db_session.close()

@router.post("/polls/{poll_id}/unarchive")
def unarchive_poll(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        poll.archived = False
        db_session.commit()
        return {"detail": "Poll unarchived"}
    finally:
        db_session.close()

# Activate/Deactivate by slug (code)
@router.post("/polls/by-slug/{slug}/activate")
def activate_poll_by_slug(slug: str, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(func.lower(models.Poll.slug) == func.lower(slug)).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found for slug")
        poll.is_active = True
        poll.start_time = datetime.utcnow()
        db_session.commit()
        return {"detail": "Poll activated", "id": poll.id}
    finally:
        db_session.close()

@router.post("/polls/by-slug/{slug}/deactivate")
def deactivate_poll_by_slug(slug: str, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(func.lower(models.Poll.slug) == func.lower(slug)).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found for slug")
        poll.is_active = False
        poll.end_time = datetime.utcnow()
        db_session.commit()
        return {"detail": "Poll deactivated", "id": poll.id}
    finally:
        db_session.close()


# ---------- CSV Export ----------
@router.get("/polls/{poll_id}/export.csv")
def export_poll_csv(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        # Compute per-question summaries
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["poll_id","title","type","question_index","question_id","question_text","choice_id","choice_text","votes","percent","is_correct"]) 
        for idx, question in enumerate(poll.questions, start=1):
            choices = question.choices
            # total votes for question
            total_votes = sum(db_session.query(models.Vote).filter(models.Vote.choice_id == c.id).count() for c in choices) or 1
            for c in choices:
                count = db_session.query(models.Vote).filter(models.Vote.choice_id == c.id).count()
                pct = round((count / total_votes) * 100)
                writer.writerow([poll.id, poll.title, getattr(poll, 'poll_type', 'trivia'), idx, question.id, question.text, c.id, c.text, count, pct, bool(getattr(c, 'is_correct', False))])
        csv_bytes = output.getvalue().encode('utf-8')
        headers = {"Content-Disposition": f"attachment; filename=poll_{poll_id}_summary.csv"}
        return Response(content=csv_bytes, media_type="text/csv", headers=headers)
    finally:
        db_session.close()


# ---------- Results ----------
@router.get("/polls/{poll_id}/results")
def poll_results(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
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
def poll_winners(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
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


@router.get("/polls/{poll_id}/leaderboard")
def trivia_leaderboard(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
    """Return trivia leaderboard sorted by correct answers desc (and timestamp asc)."""
    db_session = db.SessionLocal()
    try:
        poll = db_session.query(models.Poll).filter(models.Poll.id == poll_id).first()
        if not poll:
            raise HTTPException(status_code=404, detail="Poll not found")
        if getattr(poll, "poll_type", "trivia") != "trivia":
            raise HTTPException(status_code=400, detail="Leaderboard is only applicable for trivia polls")
        total_questions = len(poll.questions)
        correct_choice_ids = set(c.id for q in poll.questions for c in q.choices if getattr(c, "is_correct", False))
        participants = db_session.query(models.Participant).filter(models.Participant.poll_id == poll_id).all()
        rows = []
        for p in participants:
            votes = db_session.query(models.Vote).filter(models.Vote.participant_id == p.id).all()
            correct = sum(1 for v in votes if v.choice_id in correct_choice_ids)
            rows.append({
                "participant_id": p.id,
                "name": p.name,
                "company": p.company,
                "correct_count": correct,
                "total_questions": total_questions,
                "percent": (round((correct / total_questions) * 100) if total_questions else 0)
            })
        # Sort by correct desc, then name asc
        rows.sort(key=lambda r: (-r["correct_count"], (r["name"] or "")))
        return {"poll_id": poll.id, "title": poll.title, "rows": rows}
    finally:
        db_session.close()


@router.post("/polls/{poll_id}/pick-winner")
def pick_random_winner(poll_id: int, _: models.User = Depends(auth.get_current_admin_user)):
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