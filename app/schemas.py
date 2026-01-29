from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

# ---------- Auth ----------
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    username: Optional[str] = None


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=150)
    password: str = Field(..., min_length=6)


# ---------- Poll ----------
class ChoiceCreate(BaseModel):
    text: str = Field(..., max_length=255)


class QuestionCreate(BaseModel):
    text: str
    choices: List[ChoiceCreate]


class PollCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    questions: List[QuestionCreate]


class ChoiceRead(BaseModel):
    id: int
    text: str

    class Config:
        from_attributes = True


class QuestionRead(BaseModel):
    id: int
    text: str
    choices: List[ChoiceRead]

    class Config:
        from_attributes = True


class PollRead(BaseModel):
    id: int
    title: str
    description: Optional[str] = None
    is_active: bool
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    questions: List[QuestionRead]

    class Config:
        from_attributes = True


# ---------- Participant ----------
class ParticipantCreate(BaseModel):
    name: str = Field(..., max_length=150)
    company: Optional[str] = Field(None, max_length=150)


class VoteCreate(BaseModel):
    question_id: int
    choice_id: int


class VoteSubmit(BaseModel):
    participant: ParticipantCreate
    votes: List[VoteCreate]