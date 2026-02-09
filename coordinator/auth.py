"""JWT token generation and validation."""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 5


def create_jwt_ticket(user_id: str, target_node_id: str, project: str = "free-tier") -> str:
    """
    Create a JWT ticket for authorization.
    
    Args:
        user_id: The requester's ID
        target_node_id: The worker node that will process the request
        project: Tier/project identifier
        
    Returns:
        Encoded JWT token
    """
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    payload = {
        "sub": user_id,
        "target_node": target_node_id,
        "aud": "troop-worker",
        "exp": expire,
        "project": project,
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def verify_jwt_ticket(token: str) -> Optional[dict]:
    """
    Verify and decode a JWT ticket.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
            audience="troop-worker"
        )
        return payload
    except JWTError:
        return None
