"""
Stripe integration for payments and subscriptions
Handles pricing plans, subscriptions, webhooks
"""

import os
import stripe
from typing import Optional
from sqlalchemy.orm import Session
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Initialize Stripe
stripe.api_key = os.getenv("STRIPE_SECRET_KEY", "sk_test_your_key")

# Pricing configuration
PRICING_PLANS = {
    "pro_monthly": {
        "amount": 2900,  # $29.00 in cents
        "interval": "month",
        "name": "Pro Plan (Monthly)",
        "description": "Unlimited posts, 23 diagram styles, analytics sync"
    },
    "pro_annual": {
        "amount": 29900,  # $299.00 in cents
        "interval": "year",
        "name": "Pro Plan (Annual)",
        "description": "Unlimited posts, 23 diagram styles, analytics sync"
    },
    "team": {
        "amount": 9900,  # $99.00/month for team
        "interval": "month",
        "name": "Team Plan",
        "description": "Up to 5 users, unlimited posts, team dashboard"
    }
}


# ============= Stripe Customer Management =============

def create_stripe_customer(db: Session, user_id: int, email: str, full_name: str) -> Optional[str]:
    """Create Stripe customer for user"""
    from backend.models import User
    
    try:
        customer = stripe.Customer.create(
            email=email,
            name=full_name,
            metadata={"user_id": user_id}
        )
        
        # Store Stripe customer ID
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.stripe_customer_id = customer.id
            db.commit()
        
        logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
        return customer.id
    except stripe.error.StripeError as e:
        logger.error(f"Error creating Stripe customer: {e}")
        return None


def get_or_create_stripe_customer(db: Session, user_id: int, email: str, full_name: str) -> Optional[str]:
    """Get existing Stripe customer or create new one"""
    from backend.models import User
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    if user.stripe_customer_id:
        return user.stripe_customer_id
    
    return create_stripe_customer(db, user_id, email, full_name)


# ============= Subscription Management =============

def create_checkout_session(db: Session, user_id: int, plan_id: str, email: str) -> Optional[str]:
    """Create Stripe checkout session for subscription"""
    from backend.models import User
    
    if plan_id not in PRICING_PLANS:
        logger.error(f"Invalid plan ID: {plan_id}")
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    
    try:
        # Get or create Stripe customer
        stripe_customer_id = get_or_create_stripe_customer(db, user_id, email, user.full_name)
        if not stripe_customer_id:
            return None
        
        plan_info = PRICING_PLANS[plan_id]
        
        # Create checkout session
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": plan_info["name"],
                        "description": plan_info["description"]
                    },
                    "unit_amount": plan_info["amount"],
                    "recurring": {
                        "interval": plan_info["interval"],
                        "interval_count": 1
                    }
                },
                "quantity": 1
            }],
            mode="subscription",
            success_url=os.getenv("STRIPE_SUCCESS_URL", "http://localhost:3000/dashboard?success=true"),
            cancel_url=os.getenv("STRIPE_CANCEL_URL", "http://localhost:3000/pricing?cancelled=true"),
            metadata={
                "user_id": user_id,
                "plan_id": plan_id
            }
        )
        
        logger.info(f"Created checkout session {session.id} for user {user_id}")
        return session.url
    
    except stripe.error.StripeError as e:
        logger.error(f"Error creating checkout session: {e}")
        return None


def create_subscription(db: Session, user_id: int, stripe_subscription_id: str) -> bool:
    """Create subscription record in database"""
    from backend.models import User, Subscription, SubscriptionStatus
    
    try:
        # Get Stripe subscription details
        subscription = stripe.Subscription.retrieve(stripe_subscription_id)
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # Extract plan info
        plan_id = subscription["items"].data[0]["price"]["id"]
        plan_name = next(
            (k for k, v in PRICING_PLANS.items() if k == plan_id.split("_")[0] + "_" + plan_id.split("_")[1]),
            "unknown"
        )
        
        # Create subscription record
        db_subscription = Subscription(
            user_id=user_id,
            stripe_subscription_id=stripe_subscription_id,
            stripe_customer_id=subscription.customer,
            plan_name=plan_name,
            amount=subscription["items"].data[0]["price"]["unit_amount"],
            status=SubscriptionStatus.ACTIVE if subscription.status == "active" else SubscriptionStatus.TRIAL,
            current_period_start=datetime.fromtimestamp(subscription.current_period_start),
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            trial_ends_at=datetime.fromtimestamp(subscription.trial_end) if subscription.trial_end else None
        )
        
        # Update user tier
        if "pro" in plan_name:
            user.tier = "pro"
        elif "team" in plan_name:
            user.tier = "team"
        
        user.subscription_id = stripe_subscription_id
        
        db.add(db_subscription)
        db.commit()
        
        logger.info(f"Created subscription {stripe_subscription_id} for user {user_id}")
        return True
    
    except stripe.error.StripeError as e:
        logger.error(f"Error creating subscription: {e}")
        return False


def cancel_subscription(db: Session, user_id: int) -> bool:
    """Cancel user's subscription"""
    from backend.models import User, SubscriptionStatus
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.subscription_id:
            return False
        
        # Cancel in Stripe
        stripe.Subscription.delete(user.subscription_id)
        
        # Update in database
        if user.subscription:
            user.subscription.status = SubscriptionStatus.CANCELLED
            user.subscription.cancelled_at = datetime.utcnow()
        
        user.tier = "free"
        db.commit()
        
        logger.info(f"Cancelled subscription for user {user_id}")
        return True
    
    except stripe.error.StripeError as e:
        logger.error(f"Error cancelling subscription: {e}")
        return False


def update_subscription(db: Session, user_id: int, new_plan_id: str) -> bool:
    """Update user's subscription plan"""
    from backend.models import User
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.subscription_id:
            return False
        
        if new_plan_id not in PRICING_PLANS:
            return False
        
        # Get current subscription
        subscription = stripe.Subscription.retrieve(user.subscription_id)
        
        # Update plan
        price_data = {
            "currency": "usd",
            "unit_amount": PRICING_PLANS[new_plan_id]["amount"],
            "recurring": {
                "interval": PRICING_PLANS[new_plan_id]["interval"]
            }
        }
        
        # Update subscription items
        stripe.Subscription.modify(
            user.subscription_id,
            items=[{
                "id": subscription["items"].data[0].id,
                "price": new_plan_id
            }]
        )
        
        logger.info(f"Updated subscription for user {user_id} to plan {new_plan_id}")
        return True
    
    except stripe.error.StripeError as e:
        logger.error(f"Error updating subscription: {e}")
        return False


# ============= Webhook Handlers =============

def handle_subscription_updated(event: dict, db: Session):
    """Handle subscription.updated webhook"""
    from backend.models import User, Subscription, SubscriptionStatus
    
    stripe_subscription = event["data"]["object"]
    user_id = stripe_subscription["metadata"].get("user_id")
    stripe_subscription_id = stripe_subscription["id"]
    
    if not user_id:
        return
    
    try:
        user = db.query(User).filter(User.id == user_id).first()
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == stripe_subscription_id
        ).first()
        
        if subscription:
            # Map Stripe status to our enum
            status_map = {
                "active": SubscriptionStatus.ACTIVE,
                "past_due": SubscriptionStatus.PAST_DUE,
                "canceled": SubscriptionStatus.CANCELLED,
                "trialing": SubscriptionStatus.TRIAL
            }
            
            subscription.status = status_map.get(stripe_subscription["status"], SubscriptionStatus.ACTIVE)
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription["current_period_start"])
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription["current_period_end"])
            
            db.commit()
            logger.info(f"Updated subscription {stripe_subscription_id}")
    
    except Exception as e:
        logger.error(f"Error handling subscription.updated: {e}")


def handle_invoice_payment_succeeded(event: dict, db: Session):
    """Handle invoice.payment_succeeded webhook"""
    logger.info(f"Payment succeeded for invoice {event['data']['object']['id']}")


def handle_invoice_payment_failed(event: dict, db: Session):
    """Handle invoice.payment_failed webhook"""
    from backend.models import User, Subscription, SubscriptionStatus
    
    invoice = event["data"]["object"]
    subscription_id = invoice.get("subscription")
    
    if subscription_id:
        try:
            subscription = db.query(Subscription).filter(
                Subscription.stripe_subscription_id == subscription_id
            ).first()
            
            if subscription:
                subscription.status = SubscriptionStatus.PAST_DUE
                db.commit()
                logger.warning(f"Subscription {subscription_id} marked as past due")
        
        except Exception as e:
            logger.error(f"Error handling payment failure: {e}")


def handle_customer_subscription_deleted(event: dict, db: Session):
    """Handle customer.subscription.deleted webhook"""
    from backend.models import User, Subscription, SubscriptionStatus
    
    stripe_subscription = event["data"]["object"]
    subscription_id = stripe_subscription["id"]
    
    try:
        subscription = db.query(Subscription).filter(
            Subscription.stripe_subscription_id == subscription_id
        ).first()
        
        if subscription:
            subscription.status = SubscriptionStatus.CANCELLED
            subscription.cancelled_at = datetime.utcnow()
            
            # Downgrade user to free tier
            if subscription.user:
                subscription.user.tier = "free"
            
            db.commit()
            logger.info(f"Subscription {subscription_id} deleted")
    
    except Exception as e:
        logger.error(f"Error handling subscription deletion: {e}")


# ============= Webhook Processing =============

WEBHOOK_HANDLERS = {
    "customer.subscription.updated": handle_subscription_updated,
    "customer.subscription.deleted": handle_customer_subscription_deleted,
    "invoice.payment_succeeded": handle_invoice_payment_succeeded,
    "invoice.payment_failed": handle_invoice_payment_failed,
}


def process_webhook(payload: bytes, sig_header: str, db: Session) -> tuple[bool, str]:
    """Process Stripe webhook"""
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        logger.error("Invalid webhook payload")
        return False, "Invalid payload"
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid webhook signature")
        return False, "Invalid signature"
    
    # Handle event
    event_type = event["type"]
    if event_type in WEBHOOK_HANDLERS:
        WEBHOOK_HANDLERS[event_type](event, db)
        return True, f"Processed {event_type}"
    
    return True, f"Event type {event_type} not handled"


# ============= Invoice Management =============

def get_upcoming_invoice(stripe_customer_id: str) -> Optional[dict]:
    """Get upcoming invoice for customer"""
    try:
        invoice = stripe.Invoice.upcoming(customer=stripe_customer_id)
        return {
            "amount_due": invoice.amount_due,
            "currency": invoice.currency,
            "due_date": datetime.fromtimestamp(invoice.due_date) if invoice.due_date else None,
            "next_payment_attempt": datetime.fromtimestamp(invoice.next_payment_attempt) if invoice.next_payment_attempt else None
        }
    except stripe.error.InvalidRequestError:
        # No upcoming invoice
        return None
    except stripe.error.StripeError as e:
        logger.error(f"Error getting upcoming invoice: {e}")
        return None


def get_invoices(stripe_customer_id: str, limit: int = 10) -> list:
    """Get invoices for customer"""
    try:
        invoices = stripe.Invoice.list(customer=stripe_customer_id, limit=limit)
        return [
            {
                "id": inv.id,
                "amount_paid": inv.amount_paid,
                "currency": inv.currency,
                "date": datetime.fromtimestamp(inv.date),
                "status": inv.status,
                "paid": inv.paid
            }
            for inv in invoices.data
        ]
    except stripe.error.StripeError as e:
        logger.error(f"Error getting invoices: {e}")
        return []
