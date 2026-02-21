from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from core.database import Base
from datetime import datetime, timezone

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, index=True)
    product_title = Column(String)
    price = Column(Float)
    category = Column(String)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_recurring = Column(Boolean, default=False)
