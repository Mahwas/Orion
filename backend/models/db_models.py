<<<<<<< HEAD
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from core.database import Base
from datetime import datetime, timezone


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=True)
    stripe_customer_id = Column(String, unique=True, index=True, nullable=True)

    entitlement = relationship("Entitlement", back_populates="user", uselist=False)


class Entitlement(Base):
    __tablename__ = "entitlements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    credits_balance = Column(Integer, default=0, nullable=False)
    pro_active = Column(Boolean, default=False, nullable=False)
    pro_subscription_id = Column(String, nullable=True)

    user = relationship("User", back_populates="entitlement")


class WebhookEvent(Base):
    """Tracks processed Stripe webhook events for idempotency."""
    __tablename__ = "webhook_events"

    stripe_event_id = Column(String, primary_key=True, index=True)
    event_type = Column(String, nullable=True)
    processed_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


=======
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from core.database import Base
from datetime import datetime, timezone

>>>>>>> origin/feature/reasoningLLM
class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    product_title = Column(String)
    price = Column(Float)
    category = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_recurring = Column(Boolean, default=False)
