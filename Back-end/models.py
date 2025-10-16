# models.py

import os
import enum
from datetime import datetime
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey,
    Boolean,
    Enum,
)
from dotenv import load_dotenv
from sqlalchemy.orm import relationship, declarative_base

# Load environment variables from a .env file
load_dotenv()

# --- Database Connection Setup ---
# Securely build the database URL from environment variables.
# This prevents hardcoding credentials in the source code.
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError("One or more database environment variables are not set in the .env file.")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# The declarative_base() function is used to create a base class that our models will inherit from.
Base = declarative_base()


# --- Enums for controlled vocabularies ---
# Using Enums makes the data consistent and less prone to typos.

class PlayerRole(enum.Enum):
    BATSMAN = "Batsman"
    BOWLER = "Bowler"
    ALL_ROUNDER = "All-Rounder"
    WICKET_KEEPER = "Wicket-Keeper"

class MatchStatus(enum.Enum):
    SCHEDULED = "Scheduled"
    LIVE = "Live"
    COMPLETED = "Completed"
    ABANDONED = "Abandoned"

class TossDecision(enum.Enum):
    BAT = "Bat"
    FIELD = "Field"


# --- Table Models ---

class User(Base):
    """Represents a registered user in the application."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, index=True)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # A user can be a captain of multiple teams.
    teams_captained = relationship("Team", back_populates="captain")


class Team(Base):
    """Represents a cricket team."""
    __tablename__ = "teams"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    captain_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationship to the User who is the captain
    captain = relationship("User", back_populates="teams_captained")
    # Relationship to the list of players in this team
    players = relationship("Player", back_populates="team", cascade="all, delete-orphan")


class Player(Base):
    """Links a User to a Team, defining their role within that team."""
    __tablename__ = "players"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    role = Column(Enum(PlayerRole), nullable=False)

    # Relationships to easily access User and Team info from a Player object
    user = relationship("User")
    team = relationship("Team", back_populates="players")


class Tournament(Base):
    """Represents a league or tournament."""
    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True, nullable=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)

    # A tournament has many matches
    matches = relationship("Match", back_populates="tournament")


class Match(Base):
    """Represents a single cricket match between two teams."""
    __tablename__ = "matches"

    id = Column(Integer, primary_key=True, index=True)
    match_date = Column(DateTime, nullable=False)
    venue = Column(String)
    status = Column(Enum(MatchStatus), default=MatchStatus.SCHEDULED, nullable=False)

    tournament_id = Column(Integer, ForeignKey("tournaments.id"))
    team1_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    team2_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    
    toss_winner_id = Column(Integer, ForeignKey("teams.id"))
    toss_decision = Column(Enum(TossDecision))
    winner_id = Column(Integer, ForeignKey("teams.id"))

    # Relationships
    tournament = relationship("Tournament", back_populates="matches")
    team1 = relationship("Team", foreign_keys=[team1_id])
    team2 = relationship("Team", foreign_keys=[team2_id])
    toss_winner = relationship("Team", foreign_keys=[toss_winner_id])
    winner = relationship("Team", foreign_keys=[winner_id])
    
    # A match has innings
    innings = relationship("Inning", back_populates="match", cascade="all, delete-orphan")


class Inning(Base):
    """Represents one of the two innings in a match."""
    __tablename__ = "innings"

    id = Column(Integer, primary_key=True, index=True)
    match_id = Column(Integer, ForeignKey("matches.id"), nullable=False)
    batting_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    bowling_team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    total_runs = Column(Integer, default=0)
    wickets = Column(Integer, default=0)
    overs_bowled = Column(Integer, default=0)
    balls_bowled = Column(Integer, default=0)
    is_completed = Column(Boolean, default=False)
    
    # Relationships
    match = relationship("Match", back_populates="innings")
    batting_team = relationship("Team", foreign_keys=[batting_team_id])
    bowling_team = relationship("Team", foreign_keys=[bowling_team_id])

    # An inning is composed of many deliveries
    deliveries = relationship("Delivery", back_populates="inning", cascade="all, delete-orphan")


class Delivery(Base):
    """Represents a single ball bowled in an inning. This is the most granular data."""
    __tablename__ = "deliveries"

    id = Column(Integer, primary_key=True, index=True)
    inning_id = Column(Integer, ForeignKey("innings.id"), nullable=False)
    
    # We link to the Player, not the User, as a User can be on multiple teams.
    batsman_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    bowler_id = Column(Integer, ForeignKey("players.id"), nullable=False)

    runs_scored = Column(Integer, default=0)
    is_extra = Column(Boolean, default=False)
    extra_type = Column(String) # 'wide', 'noball', 'byes', 'legbyes'
    is_wicket = Column(Boolean, default=False)
    wicket_type = Column(String) # 'bowled', 'caught', 'lbw', etc.
    
    # Relationships
    inning = relationship("Inning", back_populates="deliveries")
    batsman = relationship("Player", foreign_keys=[batsman_id])
    bowler = relationship("Player", foreign_keys=[bowler_id])