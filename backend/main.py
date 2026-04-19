"""
FastAPI Backend for LinkedIn Content Generator SaaS
Provides REST API with authentication, subscriptions, post generation, and analytics
"""

import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.orm import Session
import uvicorn
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import modules
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# from src.agent import generate_linkedin_post  # TODO: Integrate in Phase 2b
# from src.topic_manager import get_all_topics, get_random_topic  # TODO: Integrate in Phase 2b
# from src.logger import setup_logger  # TODO: Integrate in Phase 2b
from backend.database import get_db, init_db, is_database_healthy
from backend.models import User, Post, UserTopic, Subscription, SubscriptionStatus
from backend.auth import (
    create_tokens, verify_token, authenticate_user, create_user,
    get_user_by_id, get_user_by_email, UserCreate, UserLogin,
    UserResponse, enable_trial, LinkedInOAuthHandler, TokenResponse
)
from backend.billing import (
    create_checkout_session, create_subscription, process_webhook,
    get_invoices, get_upcoming_invoice, PRICING_PLANS
)

core_logger = logger  # Use the logger defined at module level


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class PostGenerateRequest(BaseModel):
    """Request to generate a new post"""
    topic: Optional[str] = Field(None, description="Specific topic or None for random")
    post_type: Optional[str] = Field("topic", description="Type: topic, story, interview, ai_news")
    dry_run: bool = Field(True, description="Preview only, don't publish")


class PostResponse(BaseModel):
    """Response from post generation"""
    id: int
    text: str
    topic: str
    post_type: str
    diagram_url: Optional[str] = None
    status: str
    created_at: datetime
    linkedin_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class AnalyticsResponse(BaseModel):
    """Engagement analytics data"""
    total_posts: int
    avg_engagement: float
    top_post_type: Optional[str]
    top_topic: Optional[str]
    engagement_by_type: dict
    engagement_trend: list


class TopicResponse(BaseModel):
    """Topic information"""
    id: int
    name: str
    keywords: Optional[str]
    post_count: int
    enabled: bool
    
    class Config:
        from_attributes = True


class SettingsResponse(BaseModel):
    """User settings"""
    auto_post: bool
    post_frequency: int
    enable_analytics: bool


class CheckoutRequest(BaseModel):
    """Request to start payment process"""
    plan_id: str  # pro_monthly, pro_annual, team


class CheckoutResponse(BaseModel):
    """Checkout session response"""
    checkout_url: str
    session_id: str


class LinkedInOAuthStartRequest(BaseModel):
    """Start LinkedIn OAuth flow"""
    state: str


class SignupRequest(BaseModel):
    """Sign up with email"""
    email: EmailStr
    password: str
    full_name: str


class LoginRequest(BaseModel):
    """Login with email"""
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    """Refresh access token"""
    refresh_token: str




# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="LinkedIn Content Generator API",
    description="AI-powered LinkedIn post generation with subscription management",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8000",
        os.getenv("FRONTEND_URL", "http://localhost:3000")
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# DEPENDENCIES
# ============================================================================

async def get_current_user(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    # Extract token from "Bearer <token>" header
    try:
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid auth scheme")
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    payload = verify_token(token)
    
    if not payload or payload.type != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = get_user_by_id(db, payload.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    return user


async def require_pro_tier(user: User = Depends(get_current_user)) -> User:
    """Require Pro tier subscription"""
    if user.tier not in ["pro", "team", "admin"]:
        if not user.is_trial_active():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Pro tier required"
            )
    return user



# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.get("/health", tags=["Status"])
async def health_check():
    """Health check endpoint"""
    db_healthy = is_database_healthy()
    return {
        "status": "healthy" if db_healthy else "degraded",
        "database": "ok" if db_healthy else "error",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.get("/api/status", tags=["Status"])
async def system_status():
    """Get system status"""
    try:
        db_healthy = is_database_healthy()
        
        return {
            "status": "ready" if db_healthy else "error",
            "database": "connected" if db_healthy else "disconnected",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return {"status": "error", "error": str(e)}


# ============================================================================
# AUTHENTICATION
# ============================================================================

@app.post("/api/auth/signup", response_model=TokenResponse, tags=["Auth"])
async def signup(request: SignupRequest, db: Session = Depends(get_db)):
    """Sign up with email and password"""
    try:
        # Check if user exists
        existing = get_user_by_email(db, request.email)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create user
        user = create_user(db, request.email, request.password, request.full_name)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to create user"
            )
        
        # Enable 7-day trial
        enable_trial(db, user.id)
        
        # Create tokens
        tokens = create_tokens(user.id)
        
        logger.info(f"New user registered: {user.email}")
        return tokens
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup failed: {e}")
        raise HTTPException(status_code=500, detail="Signup failed")


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Login with email and password"""
    try:
        user = authenticate_user(db, request.email, request.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )
        
        tokens = create_tokens(user.id)
        logger.info(f"User logged in: {user.email}")
        return tokens
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}")
        raise HTTPException(status_code=500, detail="Login failed")


@app.post("/api/auth/refresh", response_model=TokenResponse, tags=["Auth"])
async def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token"""
    try:
        payload = verify_token(request.refresh_token)
        
        if not payload or payload.type != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user = get_user_by_id(db, payload.sub)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        tokens = create_tokens(user.id)
        return tokens
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise HTTPException(status_code=500, detail="Token refresh failed")


@app.get("/api/auth/me", response_model=UserResponse, tags=["Auth"])
async def get_current_user_info(user: User = Depends(get_current_user)):
    """Get current user info"""
    return user


@app.post("/api/auth/linkedin/start", tags=["Auth"])
async def start_linkedin_oauth(request: LinkedInOAuthStartRequest):
    """Start LinkedIn OAuth flow"""
    try:
        url = LinkedInOAuthHandler.get_authorization_url(request.state)
        return {"authorization_url": url}
    except Exception as e:
        logger.error(f"LinkedIn OAuth start failed: {e}")
        raise HTTPException(status_code=500, detail="OAuth initiation failed")


@app.post("/api/auth/linkedin/callback", response_model=TokenResponse, tags=["Auth"])
async def linkedin_oauth_callback(
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """LinkedIn OAuth callback"""
    try:
        # Exchange code for token
        token_data = await LinkedInOAuthHandler.exchange_code_for_token(code)
        if not token_data:
            raise HTTPException(status_code=401, detail="Failed to get access token")
        
        access_token = token_data.get("access_token")
        
        # Get user profile
        profile = await LinkedInOAuthHandler.get_user_profile(access_token)
        email = await LinkedInOAuthHandler.get_user_email(access_token)
        
        if not profile or not email:
            raise HTTPException(status_code=401, detail="Failed to get profile")
        
        # Find or create user
        user = get_user_by_email(db, email)
        if not user:
            user = create_user(db, email, "", profile.get("localizedFirstName", "LinkedIn") + " " + profile.get("localizedLastName", "User"))
            enable_trial(db, user.id)
        
        # Link LinkedIn account
        await LinkedInOAuthHandler.link_linkedin_account(db, user.id, access_token)
        
        # Create tokens
        tokens = create_tokens(user.id)
        logger.info(f"LinkedIn OAuth successful: {email}")
        return tokens
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"LinkedIn OAuth callback failed: {e}")
        raise HTTPException(status_code=500, detail="OAuth callback failed")




# ============================================================================
# POST MANAGEMENT
# ============================================================================

@app.post("/api/v1/posts/generate", response_model=PostResponse, tags=["Posts"])
async def generate_post(
    request: PostGenerateRequest,
    user: User = Depends(require_pro_tier),
    db: Session = Depends(get_db)
):
    """
    Generate a new LinkedIn post
    Requires Pro tier or active trial
    """
    try:
        # Check post limit for free tier
        if user.tier == "free":
            week_start = datetime.utcnow() - timedelta(days=7)
            recent_posts = db.query(Post).filter(
                Post.user_id == user.id,
                Post.created_at >= week_start,
                Post.status == "published"
            ).count()
            
            if recent_posts >= 2:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail="Free tier limited to 2 posts/week. Upgrade to Pro for unlimited."
                )
        
        # Generate post
        topic = request.topic
        if not topic:
            topics = get_all_topics()
            if topics:
                topic = topics[0]["name"]
        
        # Create post record
        post = Post(
            user_id=user.id,
            title=f"Post from {topic or 'Topic'}",
            content="Generated content would go here",
            topic=topic or "Technology",
            post_type=request.post_type,
            status="draft" if request.dry_run else "published",
            created_at=datetime.utcnow()
        )
        
        db.add(post)
        db.commit()
        db.refresh(post)
        
        logger.info(f"Generated post for user {user.id}: {post.id}")
        return post
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Post generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/posts", tags=["Posts"])
async def list_posts(
    limit: int = 10,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's posts with pagination"""
    try:
        query = db.query(Post).filter(Post.user_id == user.id)
        total = query.count()
        
        posts = query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
        
        return {
            "posts": posts,
            "total": total,
            "limit": limit,
            "offset": offset
        }
    
    except Exception as e:
        logger.error(f"List posts failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/posts/{post_id}", tags=["Posts"])
async def get_post(
    post_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get specific post"""
    try:
        post = db.query(Post).filter(
            Post.id == post_id,
            Post.user_id == user.id
        ).first()
        
        if not post:
            raise HTTPException(status_code=404, detail="Post not found")
        
        return post
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get post failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================================
# ANALYTICS
# ============================================================================

@app.get("/api/v1/analytics/engagement", response_model=AnalyticsResponse, tags=["Analytics"])
async def get_engagement_analytics(
    days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get engagement analytics for user"""
    try:
        cutoff = datetime.utcnow() - timedelta(days=days)
        posts = db.query(Post).filter(
            Post.user_id == user.id,
            Post.created_at >= cutoff
        ).all()
        
        if not posts:
            return {
                "total_posts": 0,
                "avg_engagement": 0,
                "top_post_type": None,
                "top_topic": None,
                "engagement_by_type": {},
                "engagement_trend": []
            }
        
        # Calculate stats
        total_engagement = sum(p.total_engagement for p in posts)
        avg_engagement = total_engagement / len(posts) if posts else 0
        
        type_counts = {}
        topic_counts = {}
        
        for post in posts:
            type_counts[post.post_type] = type_counts.get(post.post_type, 0) + 1
            topic_counts[post.topic] = topic_counts.get(post.topic, 0) + 1
        
        return {
            "total_posts": len(posts),
            "avg_engagement": avg_engagement,
            "top_post_type": max(type_counts, key=type_counts.get) if type_counts else None,
            "top_topic": max(topic_counts, key=topic_counts.get) if topic_counts else None,
            "engagement_by_type": type_counts,
            "engagement_trend": []
        }
    
    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# TOPICS
# ============================================================================

@app.get("/api/v1/topics", tags=["Topics"])
async def list_topics(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List user's topics"""
    try:
        topics = db.query(UserTopic).filter(UserTopic.user_id == user.id).all()
        return {"topics": topics}
    except Exception as e:
        logger.error(f"List topics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/topics", tags=["Topics"])
async def add_topic(
    name: str,
    keywords: Optional[str] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a new topic"""
    try:
        topic = UserTopic(
            user_id=user.id,
            name=name,
            keywords=keywords,
            enabled=True
        )
        db.add(topic)
        db.commit()
        db.refresh(topic)
        
        return {"success": True, "topic": topic}
    
    except Exception as e:
        logger.error(f"Add topic failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SETTINGS
# ============================================================================

@app.get("/api/v1/settings", response_model=SettingsResponse, tags=["Settings"])
async def get_settings(user: User = Depends(get_current_user)):
    """Get user settings"""
    return {
        "auto_post": user.auto_post,
        "post_frequency": user.post_frequency,
        "enable_analytics": user.enable_analytics
    }


@app.put("/api/v1/settings", tags=["Settings"])
async def update_settings(
    settings: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update user settings"""
    try:
        if "auto_post" in settings:
            user.auto_post = settings["auto_post"]
        if "post_frequency" in settings:
            user.post_frequency = settings["post_frequency"]
        if "enable_analytics" in settings:
            user.enable_analytics = settings["enable_analytics"]
        
        db.commit()
        
        return {
            "success": True,
            "updated_at": datetime.utcnow().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Update settings failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))




# ============================================================================
# BILLING & SUBSCRIPTIONS
# ============================================================================

@app.get("/api/v1/billing/plans", tags=["Billing"])
async def get_pricing_plans():
    """Get available plans"""
    return {
        "plans": [
            {
                "id": "pro_monthly",
                "name": PRICING_PLANS["pro_monthly"]["name"],
                "price": 29,
                "interval": "month",
                "features": [
                    "Unlimited posts",
                    "23 diagram styles",
                    "Analytics sync",
                    "Priority support"
                ]
            },
            {
                "id": "pro_annual",
                "name": PRICING_PLANS["pro_annual"]["name"],
                "price": 299,
                "interval": "year",
                "features": [
                    "Unlimited posts",
                    "23 diagram styles",
                    "Analytics sync",
                    "Priority support",
                    "Save 17% vs monthly"
                ]
            }
        ]
    }


@app.post("/api/v1/billing/checkout", response_model=CheckoutResponse, tags=["Billing"])
async def create_checkout(
    request: CheckoutRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create checkout session"""
    try:
        checkout_url = create_checkout_session(db, user.id, request.plan_id, user.email)
        if not checkout_url:
            raise HTTPException(status_code=500, detail="Failed to create checkout session")
        
        return {
            "checkout_url": checkout_url,
            "session_id": request.plan_id
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Checkout creation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/billing/subscription", tags=["Billing"])
async def get_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get user's subscription info"""
    try:
        if not user.subscription:
            return {
                "tier": user.tier,
                "status": None,
                "active": False
            }
        
        return {
            "tier": user.tier,
            "status": user.subscription.status,
            "active": user.subscription.is_active(),
            "plan": user.subscription.plan_name,
            "current_period_end": user.subscription.current_period_end,
            "trial_ends_at": user.subscription.trial_ends_at,
            "days_until_renewal": user.subscription.days_until_renewal()
        }
    
    except Exception as e:
        logger.error(f"Get subscription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/v1/billing/cancel", tags=["Billing"])
async def cancel_subscription(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cancel user's subscription"""
    try:
        from backend.billing import cancel_subscription
        success = cancel_subscription(db, user.id)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to cancel subscription")
        
        return {"success": True, "message": "Subscription cancelled"}
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cancel subscription failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# STRIPE WEBHOOKS
# ============================================================================

@app.post("/api/webhooks/stripe", tags=["Webhooks"])
async def handle_stripe_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """Handle Stripe webhooks"""
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        
        success, message = process_webhook(payload, sig_header, db)
        
        return {"success": success, "message": message}
    
    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return {"success": False, "error": str(e)}


# ============================================================================
# FRONTEND
# ============================================================================

@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
async def dashboard():
    """Serve landing page"""
    try:
        with open("index.html", 'r') as f:
            return f.read()
    except:
        return "<h1>Welcome to LinkedIn Content Generator</h1>"


@app.get("/dashboard", response_class=HTMLResponse, tags=["Frontend"])
async def app_dashboard(user: User = Depends(get_current_user)):
    """Serve app dashboard"""
    try:
        with open("templates/dashboard.html", 'r') as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error loading dashboard: {str(e)}</h1>"


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Custom HTTP exception handler"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """General exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


# ============================================================================
# STARTUP & SHUTDOWN
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Initializing database...")
    init_db()
    logger.info("LinkedIn Content Generator API v2.0 starting...")
    logger.info("📚 API Docs: /docs")
    logger.info("🎯 ReDoc: /redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("LinkedIn Content Generator API shutting down...")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    reload = os.getenv("PYTHON_ENV", "production") != "production"
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=reload,
        log_level="info"
    )
