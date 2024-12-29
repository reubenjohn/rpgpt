from contextlib import contextmanager
from dataclasses import asdict
import json
from typing import Any
from sqlalchemy import create_engine, Column, Integer, String, Text, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from token_world.llm.xplore.session_state import get_active_storyline


DB_PATH = "sqlite:///chat_history.db"

Base: Any = declarative_base()
engine = create_engine(DB_PATH)
Session = sessionmaker(bind=engine)

Message = dict[str, str]


def dataclass_to_json(dataclass_instance):
    return json.dumps(asdict(dataclass_instance))


@contextmanager
def session_scope():
    session = Session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


class StorylineModel(Base):
    __tablename__ = "storylines"
    name = Column(String, primary_key=True, nullable=False)
    description = Column(Text, nullable=False)


class MessageModel(Base):
    __tablename__ = "messages"
    storyline_name = Column(String, primary_key=True, nullable=False)
    id = Column(Integer, primary_key=True, nullable=False)
    content = Column(Text, nullable=False)

    @property
    def content_dumps(self) -> str:
        return str(self.content)

    @property
    def content_dict(self) -> Message:
        return json.loads(self.content)  # type: ignore

    @property
    def content_val(self) -> str:
        return self.content_dict["content"]


class SummaryModel(Base):
    __tablename__ = "summaries"
    storyline_name = Column(String, primary_key=True, nullable=False)
    summary_until_id = Column(Integer, primary_key=True)
    content = Column(Text, nullable=False)


class AgentGoalModel(Base):
    __tablename__ = "agent_goals"
    storyline_name = Column(String, primary_key=True, nullable=False)
    name = Column(String, primary_key=True, nullable=False)
    description = Column(Text, nullable=False)
    completed = Column(Boolean, nullable=False)
    persistence = Column(Text, nullable=False)


class MilestoneModel(Base):
    __tablename__ = "milestones"
    storyline_name = Column(String, primary_key=True, nullable=False)
    name = Column(String, primary_key=True, nullable=False)
    order = Column(Integer, primary_key=False, nullable=False)
    description = Column(Text, nullable=False)
    completed = Column(Boolean, nullable=False)


class CharacterModel(Base):
    __tablename__ = "characters"
    storyline_name = Column(String, primary_key=True, nullable=False)
    type = Column(String, primary_key=True, nullable=False)
    name = Column(Text, nullable=False)


class PropertyModel(Base):
    __tablename__ = "properties"
    key = Column(String, primary_key=True, nullable=False)
    value = Column(Text, nullable=False)


# Database setup
def initialize_db():
    Base.metadata.create_all(engine)


def get_character_name(character_type: str) -> str:
    with session_scope() as session:
        player = (
            session.query(CharacterModel)
            .where(CharacterModel.storyline_name == get_active_storyline())
            .where(CharacterModel.type == character_type)
            .first()
        )
        return player.name if player else "Player"


def get_player1_name() -> str:
    return get_character_name("player1")


def get_character1_name() -> str:
    return get_character_name("character1")


# Save message to database
def add_message_to_db(message: Message, session):
    message_model = MessageModel(storyline_name=get_active_storyline(), content=json.dumps(message))
    session.add(message_model)
    return message_model


def save_agent_goal(goal: AgentGoalModel):
    with session_scope() as session:
        session.add(goal)


def load_goals_from_db() -> list[AgentGoalModel]:
    with session_scope() as session:
        return (
            session.query(AgentGoalModel)
            .where(AgentGoalModel.storyline_name == get_active_storyline())
            .order_by(AgentGoalModel.name)
            .all()
        )


def get_all_tables():
    with engine.connect() as connection:
        result = connection.execute(text("SELECT name, sql FROM sqlite_master WHERE type='table';"))
        return [(name, sql) for name, sql in result]
