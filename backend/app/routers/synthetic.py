from fastapi import APIRouter, HTTPException, Request, Response, Cookie, Depends
from typing import Optional, List, Dict, Any
import uuid
from datetime import datetime
import json
from ..db.db import get_db, populate_database
from ..db.models import AnalyticsLog
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

router = APIRouter(prefix="/_synthetic", tags=["synthetic"])

# In-memory storage for sessions
sessions: Dict[str, Dict[str, Any]] = {}

@router.post("/new_session")
async def new_session(seed: Optional[int] = None, response: Response = None):
    """Create a new session with optional seed for reproducible data"""
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        "created_at": datetime.utcnow(),
        "seed": seed
    }
    
    # Set session cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        max_age=3600,
        samesite="lax"
    )
    
    return {"session_id": session_id}

@router.post("/log_event")
async def log_event(
    request: Request,
    event: Dict[str, Any],
    session_id: Optional[str] = None,  # Accept as query parameter
    db: Session = Depends(get_db)
):
    """Log a custom event"""
    try:
        # Get session_id from query parameter (now auth token for logged users)
        if not session_id:
            session_id = request.query_params.get("session_id")
        
        # If still no session_id, create a new anonymous one
        if not session_id:
            session_id = f"anonymous_{uuid.uuid4()}"
        
        # Parse the event data properly
        # The frontend sends: {"actionType": "scroll", "payload": {...}}
        action_type = event.get("actionType", "CUSTOM")
        payload_data = event.get("payload", {})
        
        # Determine if this is an authenticated user (session_id is a JWT token)
        is_authenticated = not session_id.startswith("anonymous_")
        
        # Create analytics log
        log = AnalyticsLog(
            session_id=session_id,
            event_type=action_type,  # Use actionType from the parsed event
            event_data=json.dumps(event),
            timestamp=datetime.utcnow()
        )
        
        # Save to database
        db.add(log)
        db.commit()
        
        return {
            "status": "success", 
            "session_id": session_id,
            "logged_action": action_type,
            "is_authenticated": is_authenticated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/logs")
async def get_logs(
    request: Request,
    session_id: Optional[str] = None,  # Accept as query parameter
    db: Session = Depends(get_db)
):
    """Get logs for a session"""
    # Get session_id from query parameter (now auth token for logged users)
    if not session_id:
        session_id = request.query_params.get("session_id")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="No session ID provided")
    
    # Special case: if session_id is "all", return all logs
    if session_id == "all":
        logs = db.query(AnalyticsLog).order_by(AnalyticsLog.timestamp.desc()).all()
    else:
        logs = db.query(AnalyticsLog).filter(
            AnalyticsLog.session_id == session_id
        ).order_by(AnalyticsLog.timestamp.desc()).all()
    
    return {
        "logs": [
            {
                "id": log.id,
                "event_type": log.event_type,  # Use the correct field name
                "session_id": log.session_id,
                "event_data": log.event_data,
                "timestamp": log.timestamp.isoformat() if log.timestamp is not None else None
            }
            for log in logs
        ]
    }

@router.post("/reset")
async def reset_environment(
    seed: Optional[int] = None,
    session_id: str = Cookie(None),
    db: Session = Depends(get_db)
):
    """Reset the environment and optionally reseed"""
    if session_id:
        sessions[session_id] = {
            "created_at": datetime.utcnow(),
            "seed": seed
        }
    
    # Reset database with new seed
    populate_database(db, seed)
    
    return {"status": "ok", "seed": seed}

@router.get("/populate")
async def populate_db(db: Session = Depends(get_db)):
    """Populate database with sample data"""
    try:
        populate_database(db)
        return {"status": "success", "message": "Database populated with sample data"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))