from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.orm import relationship
from .db import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(150), unique=True, nullable=False, index=True)
    hashed_password = Column(String, nullable=False)
    is_admin = Column(Boolean, default=True)

    polls = relationship("Poll", back_populates="creator")


class Poll(Base):
    __tablename__ = "polls"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    slug = Column(String(255), unique=True, index=True, nullable=True)
    poll_type = Column(String(20), nullable=False, default="trivia")
    is_active = Column(Boolean, default=False)
    archived = Column(Boolean, default=False)
    start_time = Column(DateTime(timezone=True), nullable=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))

    creator = relationship("User", back_populates="polls")
    questions = relationship("Question", back_populates="poll", cascade="all, delete-orphan")
    participants = relationship("Participant", back_populates="poll", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    text = Column(Text, nullable=False)

    poll = relationship("Poll", back_populates="questions")
    choices = relationship("Choice", back_populates="question", cascade="all, delete-orphan")


class Choice(Base):
    __tablename__ = "choices"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("questions.id"))
    text = Column(String(255), nullable=False)
    is_correct = Column(Boolean, default=False)

    question = relationship("Question", back_populates="choices")
    votes = relationship("Vote", back_populates="choice", cascade="all, delete-orphan")


class Participant(Base):
    __tablename__ = "participants"

    id = Column(Integer, primary_key=True, index=True)
    poll_id = Column(Integer, ForeignKey("polls.id"))
    full_name = Column(String(150), nullable=False)
    company = Column(String(150), nullable=True)
    email = Column(String(255), nullable=True)

    poll = relationship("Poll", back_populates="participants")
    votes = relationship("Vote", back_populates="participant", cascade="all, delete-orphan")


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    participant_id = Column(Integer, ForeignKey("participants.id"))
    choice_id = Column(Integer, ForeignKey("choices.id"))
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())

    participant = relationship("Participant", back_populates="votes")
    choice = relationship("Choice", back_populates="votes")
    question = relationship("Question")