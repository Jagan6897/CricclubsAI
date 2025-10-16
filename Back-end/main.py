# main.py

from typing import List
from datetime import timedelta
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import crud, models, schemas, auth, security
from database import SessionLocal, engine, get_db

# This command creates all the database tables based on your models.py
models.Base.metadata.create_all(bind=engine)

app = FastAPI()

@app.get("/")
def read_root():
    """A welcome message for the root URL."""
    return {"message": "Welcome to the CricClubs AI API!"}

# --- Authentication Endpoints ---

@app.post("/users/", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Endpoint to register a new user."""
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)

@app.post("/token", response_model=schemas.Token)
def login_for_access_token(db: Session = Depends(get_db), form_data: OAuth2PasswordRequestForm = Depends()):
    """Endpoint for user login. Returns a JWT access token."""
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/users/me/", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """A protected endpoint to get the current authenticated user's details."""
    return current_user


# --- Application Endpoints ---

@app.post("/teams/", response_model=schemas.Team, status_code=status.HTTP_201_CREATED)
def create_team(
    team: schemas.TeamCreate, 
    db: Session = Depends(get_db), 
    current_user: models.User = Depends(auth.get_current_user)
):
    """Protected endpoint to create a new team. The creator becomes the captain."""
    return crud.create_team(db=db, team=team, captain_id=current_user.id)

@app.get("/teams/{team_id}", response_model=schemas.Team)
def read_team(team_id: int, db: Session = Depends(get_db)):
    """Endpoint to get the details of a single team, including its players."""
    db_team = crud.get_team_by_id(db, team_id=team_id)
    if db_team is None:
        raise HTTPException(status_code=404, detail="Team not found")
    return db_team

@app.post("/teams/{team_id}/players", response_model=schemas.Player)
def add_player_to_team(
    team_id: int,
    player: schemas.PlayerBase,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Protected endpoint to add a player to a team. (Future: check if user is captain)."""
    # First, get the team to check who the captain is
    db_team = crud.get_team_by_id(db, team_id=team_id)
    if not db_team:
        raise HTTPException(status_code=404, detail="Team not found")

    # --- AUTHORIZATION CHECK ---
    if db_team.captain_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the team captain can add players.")

    if player.team_id != team_id:
        raise HTTPException(status_code=400, detail="Team ID in URL and payload do not match.")
    return crud.add_player_to_team(db=db, player=player)

# --- Tournament and Match Endpoints ---

@app.post("/tournaments/", response_model=schemas.Tournament, status_code=status.HTTP_201_CREATED)
def create_tournament(
    tournament: schemas.TournamentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Protected endpoint to create a new tournament."""
    return crud.create_tournament(db=db, tournament=tournament)

@app.get("/tournaments/", response_model=List[schemas.Tournament])
def read_tournaments(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Endpoint to list all tournaments."""
    tournaments = crud.get_tournaments(db, skip=skip, limit=limit)
    return tournaments

@app.post("/tournaments/{tournament_id}/matches", response_model=schemas.Match, status_code=status.HTTP_201_CREATED)
def create_match_in_tournament(
    tournament_id: int,
    match: schemas.MatchCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Protected endpoint to create a new match within a specific tournament."""
    if match.team1_id == match.team2_id:
        raise HTTPException(status_code=400, detail="A team cannot play against itself.")
    return crud.create_match(db=db, match=match, tournament_id=tournament_id)

@app.get("/matches/{match_id}", response_model=schemas.Match)
def read_match(match_id: int, db: Session = Depends(get_db)):
    """Endpoint to get the details of a single match."""
    db_match = crud.get_match_by_id(db, match_id=match_id)
    if db_match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return db_match

@app.post("/matches/{match_id}/toss", response_model=schemas.Match)
def record_toss(
    match_id: int,
    toss_data: schemas.TossData,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """Protected endpoint to record the toss result for a match."""
    db_match = crud.get_match_by_id(db, match_id)
    if not db_match:
        raise HTTPException(status_code=404, detail="Match not found")
    
    if toss_data.toss_winner_id not in [db_match.team1_id, db_match.team2_id]:
        raise HTTPException(status_code=400, detail="Toss winner must be one of the two teams in the match.")

    updated_match = crud.update_match_toss(db=db, match_id=match_id, toss_data=toss_data)
    return updated_match


# --- Scoring Endpoint ---

@app.post("/matches/{match_id}/score", response_model=schemas.Match, status_code=status.HTTP_201_CREATED)
def record_delivery(
    match_id: int,
    delivery: schemas.DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(auth.get_current_user)
):
    """
    Protected endpoint for live scoring. Records a single delivery and updates the match state.
    """
    # The CRUD function now handles the core logic
    db_delivery = crud.record_delivery(db=db, match_id=match_id, delivery=delivery)

    if db_delivery is None:
        raise HTTPException(status_code=400, detail="Invalid scoring operation. Check match/inning status or IDs.")

    # Return the updated match state, including the new score
    return crud.get_match_by_id(db, match_id=match_id)