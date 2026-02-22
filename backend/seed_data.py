import asyncio
from database import engine, Base, AsyncSessionLocal
from models.orm import User, BankAccount, Transaction
import datetime

async def seed():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Create a user
        user = User(name="John Doe", email="john@example.com")
        session.add(user)
        await session.flush()

        # Create bank accounts
        checking = BankAccount(user_id=user.id, account_type="Checking", balance=1500.50)
        savings = BankAccount(user_id=user.id, account_type="Savings", balance=5000.00)
        session.add_all([checking, savings])
        await session.flush()

        # Create transactions
        transactions = [
            Transaction(account_id=checking.id, merchant="Groceries R Us", amount=85.20, category="Food", transaction_type="DEBIT"),
            Transaction(account_id=checking.id, merchant="Tech Store", amount=1200.00, category="Electronics", transaction_type="DEBIT"),
            Transaction(account_id=checking.id, merchant="Employer Inc", amount=2500.00, category="Salary", transaction_type="CREDIT"),
            Transaction(account_id=savings.id, merchant="Internal Transfer", amount=500.00, category="Transfer", transaction_type="CREDIT"),
        ]
        session.add_all(transactions)
        
        await session.commit()
        print("Database seeded successfully!")

if __name__ == "__main__":
    asyncio.run(seed())
