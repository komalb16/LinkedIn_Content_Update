"""
Database models for LinkedIn Content Generator SaaS
User, Subscription, Post, Analytics
"""

from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Float, Text, Enum, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class UserRole(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    TEAM = "team"
    ADMIN = "admin"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    TRIAL = "trial"
    PAST_DUE = "past_due"


class User(Base):
    """User account model"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    full_name = Column(String)
    
    # LinkedIn integration
    linkedin_access_token = Column(String, nullable=True)
    linkedin_person_urn = Column(String, nullable=True)
    linkedin_profile_url = Column(String, nullable=True)
    
    # Subscription
    tier = Column(Enum(UserRole), default=UserRole.FREE)
    subscription_id = Column(String, nullable=True)  # Stripe subscription ID
    
    # Settings
    auto_post = Column(Boolean, default=True)
    post_frequency = Column(Integer, default=2)  # Posts per week
    enable_analytics = Column(Boolean, default=True)
    
    # Account info
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    
    # Relationships
    subscription = relationship("Subscription", back_populates="user", uselist=False)
    posts = relationship("Post", back_populates="user", cascade="all, delete-orphan")
    topics = relationship("UserTopic", back_populates="user", cascade="all, delete-orphan")
    
    def is_trial_active(self) -> bool:
        """Check if trial period is still active"""
        if self.tier != UserRole.FREE:
            if self.subscription and self.subscription.trial_ends_at:
                return datetime.utcnow() < self.subscription.trial_ends_at
        return False
    
    def has_unlimited_posts(self) -> bool:
        """Check if user has unlimited posts (Pro or higher)"""
        return self.tier in [UserRole.PRO, UserRole.TEAM]
    
    def get_posts_per_week(self) -> int:
        """Get allowed posts per week based on tier"""
        if self.is_trial_active() or self.has_unlimited_posts():
            return 999  # Unlimited
        return 2  # Free tier


class Subscription(Base):
    """Subscription model for tracking paid plans"""
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Stripe info
    stripe_subscription_id = Column(String, unique=True)
    stripe_customer_id = Column(String)
    
    # Plan info
    plan_name = Column(String)  # "pro_monthly", "pro_annual", "team"
    amount = Column(Float)  # In cents
    currency = Column(String, default="usd")
    
    # Status tracking
    status = Column(Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE)
    current_period_start = Column(DateTime)
    current_period_end = Column(DateTime)
    trial_ends_at = Column(DateTime, nullable=True)
    
    # Dates
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="subscription")
    
    def is_active(self) -> bool:
        """Check if subscription is currently active"""
        return self.status == SubscriptionStatus.ACTIVE and self.current_period_end > datetime.utcnow()
    
    def days_until_renewal(self) -> int:
        """Days until subscription renewal"""
        if not self.is_active():
            return 0
        return (self.current_period_end - datetime.utcnow()).days


class Post(Base):
    """Generated LinkedIn post model"""
    __tablename__ = "posts"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    # Content
    title = Column(String)
    content = Column(Text)
    topic = Column(String, index=True)
    post_type = Column(String)  # topic, story, interview, news
    
    # Media
    diagram_style = Column(Integer)
    diagram_url = Column(String, nullable=True)
    
    # LinkedIn
    linkedin_post_id = Column(String, nullable=True, unique=True)
    linkedin_url = Column(String, nullable=True)
    
    # Status
    status = Column(String, default="draft")  # draft, scheduled, published, failed
    published_at = Column(DateTime, nullable=True)
    scheduled_for = Column(DateTime, nullable=True)
    
    # Engagement
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    reposts = Column(Integer, default=0)
    total_engagement = Column(Integer, default=0)
    engagement_score = Column(Float, default=0.0)
    
    # Quality metrics
    has_vulnerability = Column(Boolean, default=False)
    has_strong_cta = Column(Boolean, default=False)
    hashtag_count = Column(Integer, default=0)
    emoji_count = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    engagement_synced_at = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="posts")
    
    def is_synced(self) -> bool:
        """Check if engagement has been synced recently"""
        if not self.engagement_synced_at:
            return False
        # Sync if older than 1 hour
        return (datetime.utcnow() - self.engagement_synced_at).seconds < 3600
    
    def update_engagement(self, likes: int, comments: int, reposts: int):
        """Update engagement metrics"""
        self.likes = likes
        self.comments = comments
        self.reposts = reposts
        self.total_engagement = likes + comments + reposts
        self.engagement_synced_at = datetime.utcnow()


class UserTopic(Base):
    """User's configured topics for post generation"""
    __tablename__ = "user_topics"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    name = Column(String)
    category = Column(String, nullable=True)
    keywords = Column(String, nullable=True)  # Comma-separated
    
    enabled = Column(Boolean, default=True)
    post_count = Column(Integer, default=0)
    last_used = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="topics")


class LinkedInEngagement(Base):
    """Synced engagement data from LinkedIn"""
    __tablename__ = "linkedin_engagement"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=True)
    
    # LinkedIn data
    linkedin_post_id = Column(String, unique=True, index=True)
    
    # Metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    likes = Column(Integer, default=0)
    comments = Column(Integer, default=0)
    reposts = Column(Integer, default=0)
    followers_gained = Column(Integer, default=0)
    
    # Calculated
    engagement_rate = Column(Float, default=0.0)
    reach = Column(Integer, default=0)
    
    # Tracking
    synced_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)


class APIKey(Base):
    """API keys for programmatic access"""
    __tablename__ = "api_keys"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    
    key = Column(String, unique=True, index=True)
    name = Column(String)
    last_used = Column(DateTime, nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Track important user actions"""
    __tablename__ = "audit_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    
    action = Column(String)  # post_published, settings_changed, subscription_updated, etc.
    resource = Column(String)  # post, user, subscription
    resource_id = Column(String)
    
    details = Column(Text, nullable=True)  # JSON stringified details
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
