# crud.py

from sqlalchemy.orm import Session
import models, schemas, security

# --- User CRUD ---

def get_user_by_email(db: Session, email: str):
    """Fetches a user by their email address."""
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: schemas.UserCreate):
    """Creates a new user in the database with a hashed password."""
    hashed_password = security.get_password_hash(user.password)
    db_user = models.User(email=user.email, full_name=user.full_name, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# --- Team CRUD ---

def create_team(db: Session, team: schemas.TeamCreate, captain_id: int):
    """Creates a new team with the specified user as the captain."""
    db_team = models.Team(name=team.name, captain_id=captain_id)
    db.add(db_team)
    db.commit()
    db.refresh(db_team)
    return db_team

def get_team_by_id(db: Session, team_id: int):
    """Fetches a team by its ID, including its players and their user details."""
    return db.query(models.Team).filter(models.Team.id == team_id).first()

def add_player_to_team(db: Session, player: schemas.PlayerBase):
    """Adds a user to a team with a specific role."""
    db_player = models.Player(**player.dict())
    db.add(db_player)
    db.commit()
    db.refresh(db_player)
    return db_player

# --- Tournament & Match CRUD ---

def create_tournament(db: Session, tournament: schemas.TournamentCreate):
    """Creates a new tournament."""
    db_tournament = models.Tournament(**tournament.dict())
    db.add(db_tournament)
    db.commit()
    db.refresh(db_tournament)
    return db_tournament

def get_tournaments(db: Session, skip: int = 0, limit: int = 100):
    """Fetches all tournaments with pagination."""
    return db.query(models.Tournament).offset(skip).limit(limit).all()

def create_match(db: Session, match: schemas.MatchCreate, tournament_id: int):
    """Creates a new match within a tournament."""
    db_match = models.Match(**match.dict(), tournament_id=tournament_id)
    db.add(db_match)
    db.commit()
    db.refresh(db_match)
    return db_match

def get_match_by_id(db: Session, match_id: int):
    """Fetches a single match by its ID."""
    return db.query(models.Match).filter(models.Match.id == match_id).first()

def update_match_toss(db: Session, match_id: int, toss_data: schemas.TossData):
    """Updates a match with the toss winner and decision."""
    db_match = get_match_by_id(db, match_id)
    if not db_match:
        return None
    
    # Prevent updating toss if innings have already started
    if db_match.innings:
        return None # Or raise an exception

    db_match.toss_winner_id = toss_data.toss_winner_id
    db_match.toss_decision = toss_data.decision

    # --- AUTOMATION LOGIC ---
    # Determine batting and bowling teams
    toss_loser_id = db_match.team2_id if toss_data.toss_winner_id == db_match.team1_id else db_match.team1_id

    if toss_data.decision == models.TossDecision.BAT:
        first_batting_team_id = toss_data.toss_winner_id
        first_bowling_team_id = toss_loser_id
    else: # FIELD
        first_batting_team_id = toss_loser_id
        first_bowling_team_id = toss_data.toss_winner_id

    # Create both innings records
    inning1 = models.Inning(match_id=match_id, batting_team_id=first_batting_team_id, bowling_team_id=first_bowling_team_id)
    inning2 = models.Inning(match_id=match_id, batting_team_id=first_bowling_team_id, bowling_team_id=first_batting_team_id)
    db.add_all([inning1, inning2])

    db.commit()
    db.refresh(db_match)
    return db_match

# --- Delivery CRUD ---

def record_delivery(db: Session, match_id: int, delivery: schemas.DeliveryCreate):
    """
    Records a new ball-by-ball delivery and updates the match/inning state.
    This function contains the core scoring logic.
    """
    # 1. Fetch the inning and the associated match
    inning = db.query(models.Inning).filter(models.Inning.id == delivery.inning_id).first()
    if not inning or inning.match_id != match_id:
        return None

    match = inning.match
    
    # Prevent scoring in a completed match or inning
    if match.status == models.MatchStatus.COMPLETED or inning.is_completed:
        return None # Or raise HTTPException

    # 2. Create the delivery record
    db_delivery = models.Delivery(
        inning_id=delivery.inning_id,
        batsman_id=delivery.batsman_id,
        bowler_id=delivery.bowler_id,
        runs_scored=delivery.runs_scored,
        is_extra=delivery.is_extra,
        is_wicket=delivery.is_wicket,
        wicket_type=delivery.wicket_type
    )
    db.add(db_delivery)

    # 3. Update Inning Score
    inning.total_runs += delivery.runs_scored
    if delivery.is_extra:
        inning.total_runs += 1 # Assuming extras like wide/no-ball add 1 run + runs scored

    if delivery.is_wicket:
        inning.wickets += 1

    # 4. Update Overs and Balls
    if not delivery.is_extra: # Extras like wides and no-balls don't count as a ball bowled
        inning.balls_bowled += 1
        if inning.balls_bowled == 6:
            inning.overs_bowled += 1
            inning.balls_bowled = 0

    # 5. Update Match Status
    if match.status == models.MatchStatus.SCHEDULED:
        match.status = models.MatchStatus.LIVE

    # 6. Check for end of innings/match
    # For simplicity, we assume a 10-wicket or 20-over limit.
    is_inning_over = (inning.wickets >= 10) or (inning.overs_bowled >= 20)
    
    # Get both innings, ordered by their ID (first created is first inning)
    all_innings = sorted(match.innings, key=lambda i: i.id)
    is_first_inning = (inning.id == all_innings[0].id)

    # If the second team passes the first team's score, the match ends
    if not is_first_inning:
        first_inning_score = all_innings[0].total_runs
        if inning.total_runs > first_inning_score:
            is_inning_over = True # Chase is complete
            match.winner_id = inning.batting_team_id
            match.status = models.MatchStatus.COMPLETED

    if is_inning_over:
        inning.is_completed = True
        # If it was the second inning that just finished, determine the winner
        if not is_first_inning and not match.winner_id: # and winner not already set by chase
            first_inning_score = all_innings[0].total_runs
            if inning.total_runs > first_inning_score:
                match.winner_id = inning.batting_team_id
            elif first_inning_score > inning.total_runs:
                match.winner_id = inning.bowling_team_id
            # (Tie logic could be added here)
            match.status = models.MatchStatus.COMPLETED

    # 7. Commit all changes to the database
    db.commit()
    db.refresh(db_delivery)
    return db_delivery