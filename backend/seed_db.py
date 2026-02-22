import asyncio
from database import AsyncSessionLocal, engine, Base
from models.db_models import StripeTransaction, StripeUser, Entitlement
from datetime import datetime, timezone, timedelta

async def seed_db():
    print("Setting up database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async with AsyncSessionLocal() as db:
        # Check if we already have transactions
        from sqlalchemy import select
        result = await db.execute(select(StripeTransaction).limit(1))
        if result.scalar_one_or_none():
            print("Database already seeded.")
            return
            
        print("Seeding with mock transactions...")
        
        now = datetime.now(timezone.utc)

        # Create users with entitlements
        users = [
            StripeUser(id="u123", email="alice@example.com"),
            StripeUser(id="u124", email="bob@example.com"),
            StripeUser(id="u125", email="charlie@example.com"),
        ]
        db.add_all(users)
        await db.flush()

        # Give each user some starting credits
        entitlements = [
            Entitlement(user_id="u123", credits_balance=3, pro_active=False),
            Entitlement(user_id="u124", credits_balance=1, pro_active=False),
            Entitlement(user_id="u125", credits_balance=0, pro_active=True),  # Pro user
        ]
        db.add_all(entitlements)
        
        # User u123: Consistent bills but recent impulse buy
        transactions = [
            StripeTransaction(user_id="u123", product_title="Netflix Subscription", price=15.49, category="Entertainment", timestamp=now - timedelta(days=2), is_recurring=True),
            StripeTransaction(user_id="u123", product_title="Gym Membership", price=45.00, category="Health", timestamp=now - timedelta(days=5), is_recurring=True),
            StripeTransaction(user_id="u123", product_title="Smart Speaker", price=199.99, category="Electronics", timestamp=now - timedelta(days=1), is_recurring=False),
            StripeTransaction(user_id="u123", product_title="Electric Bill", price=85.00, category="Utilities", timestamp=now - timedelta(days=15), is_recurring=True),
            StripeTransaction(user_id="u123", product_title="Groceries", price=120.50, category="Food", timestamp=now - timedelta(days=4), is_recurring=False),

            # User u124: Frugal saving for a car
            StripeTransaction(user_id="u124", product_title="Spotify Premium", price=10.99, category="Entertainment", timestamp=now - timedelta(days=1), is_recurring=True),
            StripeTransaction(user_id="u124", product_title="Car Insurance", price=115.00, category="Insurance", timestamp=now - timedelta(days=18), is_recurring=True),
            StripeTransaction(user_id="u124", product_title="Groceries", price=65.20, category="Food", timestamp=now - timedelta(days=7), is_recurring=False),
            
            # User u125: High income luxury
            StripeTransaction(user_id="u125", product_title="Designer Shoes", price=650.00, category="Clothing", timestamp=now - timedelta(days=3), is_recurring=False),
            StripeTransaction(user_id="u125", product_title="Espresso Machine", price=1200.00, category="Home", timestamp=now - timedelta(days=10), is_recurring=False),
            StripeTransaction(user_id="u125", product_title="Equinox Membership", price=250.00, category="Health", timestamp=now - timedelta(days=14), is_recurring=True),
            StripeTransaction(user_id="u125", product_title="Fine Dining", price=320.00, category="Food", timestamp=now - timedelta(days=1), is_recurring=False),
        ]
        
        db.add_all(transactions)
        await db.commit()
        print(f"Successfully added {len(transactions)} mock transactions and {len(users)} users with entitlements.")

if __name__ == "__main__":
    asyncio.run(seed_db())
