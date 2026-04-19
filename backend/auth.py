"""
Authentication module for JWT and OAuth
Handles login, signup, LinkedIn OAuth, and token validation
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import os

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 7
TRIAL_PERIOD_DAYS = 7

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ============= Pydantic Models =============

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    sub: int  # user_id
    exp: datetime
    type: str  # "access" or "refresh"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str


class UserLogin(BaseModel):
    email: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    tier: str
    is_active: bool
    created_at: datetime
    
    class Config:
        from_attributes = True


class LinkedInOAuthRequest(BaseModel):
    code: str  # OAuth authorization code from LinkedIn
    state: str  # CSRF token


class LinkedInOAuthResponse(BaseModel):
    access_token: str
    expires_in: int
    refresh_token: Optional[str] = None


# ============= Password Hashing =============

def hash_password(password: str) -> str:
    """Hash password"""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hash"""
    return pwd_context.verify(plain_password, hashed_password)


# ============= JWT Token Handling =============

def create_access_token(user_id: int, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "type": "access",
        "iat": datetime.utcnow()
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int) -> str:
    """Create JWT refresh token"""
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode = {
        "sub": user_id,
        "exp": expire,
        "type": "refresh",
        "iat": datetime.utcnow()
    }
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_tokens(user_id: int) -> TokenResponse:
    """Create both access and refresh tokens"""
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


def verify_token(token: str) -> Optional[TokenPayload]:
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        token_type = payload.get("type")
        if user_id is None:
            return None
        
        exp = payload.get("exp")
        return TokenPayload(
            sub=user_id,
            exp=datetime.fromtimestamp(exp) if exp else datetime.utcnow(),
            type=token_type or "access"
        )
    except JWTError:
        return None


def refresh_access_token(refresh_token: str) -> Optional[str]:
    """Create new access token from refresh token"""
    payload = verify_token(refresh_token)
    if not payload or payload.type != "refresh":
        return None
    
    return create_access_token(payload.sub)


# ============= User Management =============

def create_user(db: Session, email: str, password: str, full_name: str):
    """Create new user account"""
    from backend.models import User
    
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        return None
    
    hashed_password = hash_password(password)
    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_active=True
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, email: str, password: str):
    """Authenticate user by email and password"""
    from backend.models import User
    
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    
    if not verify_password(password, user.hashed_password):
        return None
    
    return user


def get_user_by_id(db: Session, user_id: int):
    """Get user by ID"""
    from backend.models import User
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str):
    """Get user by email"""
    from backend.models import User
    return db.query(User).filter(User.email == email).first()


def enable_trial(db: Session, user_id: int):
    """Enable trial period for user"""
    from backend.models import User, Subscription, SubscriptionStatus
    from datetime import datetime, timedelta
    
    user = get_user_by_id(db, user_id)
    if not user:
        return False
    
    # Create trial subscription
    trial_ends = datetime.utcnow() + timedelta(days=TRIAL_PERIOD_DAYS)
    subscription = Subscription(
        user_id=user_id,
        stripe_subscription_id="trial_" + str(user_id),
        stripe_customer_id="",
        plan_name="trial",
        amount=0,
        status=SubscriptionStatus.TRIAL,
        current_period_start=datetime.utcnow(),
        current_period_end=trial_ends,
        trial_ends_at=trial_ends
    )
    
    db.add(subscription)
    user.tier = "pro"
    db.commit()
    return True


# ============= LinkedIn OAuth =============

class LinkedInOAuthHandler:
    """Handle LinkedIn OAuth 2.0 flow"""
    
    CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID", "")
    CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET", "")
    REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8000/auth/linkedin/callback")
    
    @staticmethod
    def get_authorization_url(state: str) -> str:
        """Get LinkedIn OAuth authorization URL"""
        params = {
            "response_type": "code",
            "client_id": LinkedInOAuthHandler.CLIENT_ID,
            "redirect_uri": LinkedInOAuthHandler.REDIRECT_URI,
            "state": state,
            "scope": "profile,email,openid"
        }
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"https://www.linkedin.com/oauth/v2/authorization?{query_string}"
    
    @staticmethod
    async def exchange_code_for_token(code: str) -> Optional[dict]:
        """Exchange authorization code for access token"""
        import httpx
        
        url = "https://www.linkedin.com/oauth/v2/accessToken"
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": LinkedInOAuthHandler.REDIRECT_URI,
            "client_id": LinkedInOAuthHandler.CLIENT_ID,
            "client_secret": LinkedInOAuthHandler.CLIENT_SECRET
        }
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, data=data)
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"LinkedIn OAuth error: {e}")
        
        return None
    
    @staticmethod
    async def get_user_profile(access_token: str) -> Optional[dict]:
        """Get user profile from LinkedIn"""
        import httpx
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Get user info
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.linkedin.com/v2/me",
                    headers=headers
                )
                if response.status_code == 200:
                    return response.json()
            except Exception as e:
                print(f"Failed to get LinkedIn profile: {e}")
        
        return None
    
    @staticmethod
    async def get_user_email(access_token: str) -> Optional[str]:
        """Get user email from LinkedIn"""
        import httpx
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    "https://api.linkedin.com/v2/emailAddress?q=members&projection=(elements*(handle~))",
                    headers=headers
                )
                if response.status_code == 200:
                    data = response.json()
                    if "elements" in data and len(data["elements"]) > 0:
                        email_obj = data["elements"][0].get("handle~")
                        if email_obj:
                            return email_obj.get("emailAddress")
            except Exception as e:
                print(f"Failed to get LinkedIn email: {e}")
        
        return None
    
    @staticmethod
    async def link_linkedin_account(db: Session, user_id: int, access_token: str):
        """Link LinkedIn account to user"""
        from backend.models import User
        
        profile = await LinkedInOAuthHandler.get_user_profile(access_token)
        if not profile:
            return False
        
        user = get_user_by_id(db, user_id)
        if not user:
            return False
        
        person_urn = profile.get("id", "")
        user.linkedin_access_token = access_token
        user.linkedin_person_urn = person_urn
        
        # Try to get profile URL
        try:
            user.linkedin_profile_url = f"https://linkedin.com/in/user"
        except:
            pass
        
        db.commit()
        return True
