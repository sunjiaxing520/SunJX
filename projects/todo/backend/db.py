import os
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine, String, Text, Integer, JSON, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env', override=False)
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./.runtime/todo.db')
(ROOT / '.runtime').mkdir(exist_ok=True)
engine = create_engine(DATABASE_URL, pool_pre_ping=True, hide_parameters=True,
    connect_args={'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {})
Session = sessionmaker(engine, expire_on_commit=False)
def now(): return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__ = 'todo_users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(String(50))
    key_cipher: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str] = mapped_column(String(100), default='kimi-k2.6')
    revision: Mapped[int] = mapped_column(Integer, default=0)
    data: Mapped[dict] = mapped_column(JSON, default=lambda: {'projects': [], 'tasks': []})

class LoginSession(Base):
    __tablename__ = 'todo_sessions'
    digest: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('todo_users.id'), index=True)
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Message(Base):
    __tablename__ = 'todo_messages'
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('todo_users.id'), index=True)
    project_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    proposal: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default='message')
    base_revision: Mapped[int] = mapped_column(Integer, default=0)
    previous_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    applied_revision: Mapped[int | None] = mapped_column(Integer, nullable=True)
