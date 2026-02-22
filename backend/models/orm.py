from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from database import Base
import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    
    # Financial Profile
    monthly_income = Column(Float, default=0.0)
    pay_cycle = Column(String, default="monthly")
    days_until_payday = Column(Integer, default=0)
    savings_goals = Column(JSON, default=list) # List of dicts
    debts = Column(JSON, default=list) # List of dicts
    
    accounts = relationship("BankAccount", back_populates="owner")

class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    account_type = Column(String) # Checking, Savings, etc.
    balance = Column(Float)
    currency = Column(String, default="USD")
    
    owner = relationship("User", back_populates="accounts")
    transactions = relationship("Transaction", back_populates="account", cascade="all, delete-orphan")

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("bank_accounts.id"))
    merchant = Column(String)
    amount = Column(Float)
    category = Column(String)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    transaction_type = Column(String) # DEBIT, CREDIT
    
    account = relationship("BankAccount", back_populates="transactions")
