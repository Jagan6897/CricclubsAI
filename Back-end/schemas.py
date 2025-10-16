# schemas.py

from pydantic import BaseModel, EmailStr
from typing import List, Optional, ForwardRef
from datetime import datetime
from models import PlayerRole, MatchStatus, TossDecision

# --- Base Schemas ---
# These are the base models with fields common to both creation and reading.

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class TeamBase(BaseModel):
    name: str

class PlayerBase(BaseModel):
    user_id: int
    team_id: int
    role: PlayerRole

class TournamentBase(BaseModel):
    name: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None

class MatchBase(BaseModel):
    match_date: datetime
    venue: Optional[str] = None

class TossData(BaseModel):
    toss_winner_id: int
    decision: TossDecision


# --- Create Schemas ---
# These models are used as input when creating new database records.

class UserCreate(UserBase):
    password: str

class TeamCreate(TeamBase):
    pass # For now, captain will be the user creating the team

class DeliveryCreate(BaseModel):
    inning_id: int
    batsman_id: int
    bowler_id: int
    runs_scored: int
    is_wicket: bool = False
    is_extra: bool = False
    wicket_type: Optional[str] = None

class TournamentCreate(TournamentBase):
    pass

class MatchCreate(MatchBase):
    team1_id: int
    team2_id: int

# --- Read Schemas ---
# These models are used as output when reading data from the API.
# They include fields like `id` and `created_at` and hide sensitive info like passwords.

class User(UserBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Player(PlayerBase):
    id: int
    user: User # Nest the User schema to show player's name/email

    class Config:
        from_attributes = True

class Team(TeamBase):
    id: int
    captain: User # Show the full captain object, not just the ID
    players: List[Player] = [] # Include the list of players

    class Config:
        from_attributes = True

class Inning(BaseModel):
    id: int
    batting_team_id: int
    bowling_team_id: int
    total_runs: int
    wickets: int
    overs_bowled: int
    balls_bowled: int
    is_completed: bool

    class Config:
        from_attributes = True


# ForwardRef is used to handle circular dependencies between Match and Tournament schemas
MatchInTournament = ForwardRef('Match')

class Tournament(TournamentBase):
    id: int
    matches: List[MatchInTournament] = []

    class Config:
        from_attributes = True

class Match(MatchBase):
    id: int
    status: MatchStatus
    team1: Team
    team2: Team
    toss_winner: Optional[Team] = None
    winner: Optional[Team] = None
    innings: List[Inning] = []
    tournament: TournamentBase # Show basic tournament info

    class Config:
        from_attributes = True

# --- Token Schemas ---
# For handling JWT authentication.

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Update the forward reference now that Match is defined
Tournament.model_rebuild()