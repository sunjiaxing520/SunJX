from datetime import datetime
from enum import Enum as PythonEnum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class AgentType(str, PythonEnum):
    CRAWLER = "crawler"
    ANALYSIS = "analysis"
    LYRICS = "lyrics"
    MUSIC = "music"


class UserAgentPermission(Base):
    __tablename__ = "user_agent_permissions"

    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    agent: Mapped[AgentType] = mapped_column(
        Enum(
            AgentType,
            name="agent_type",
            values_callable=lambda agents: [agent.value for agent in agents],
        ),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    user: Mapped["User"] = relationship(back_populates="agent_permissions")
