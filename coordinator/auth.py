"""JWT token generation and validation."""

import os
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from crypto import load_private_key, load_public_key

ALGORITHM = "RS256"  # RSA signing
ACCESS_TOKEN_EXPIRE_MINUTES = 5


def create_jwt_ticket(user_id: str, target_node_id: str, project: str = "free-tier") -> str:
    """
    Create a JWT ticket for authorization using RSA signing.
    
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
    
    private_key = load_private_key()
    token = jwt.encode(payload, private_key, algorithm=ALGORITHM)
    return token


def verify_jwt_ticket(token: str) -> Optional[dict]:
    """ using RSA public key.
    
    Args:
        token: The JWT token to verify
        
    Returns:
        Decoded payload if valid, None otherwise
    """
    try:
        public_key = load_public_key()
        payload = jwt.decode(
            token,
            public_key,
            algorithms=[ALGORITHM],
            audience="troop-worker"
        )
        return payload
    except JWTError as e:
        print(f"JWT verification failed: {e}")
        return None
