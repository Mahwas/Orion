from core.database import SessionLocal, engine, Base
from models.db_models import Transaction
from datetime import datetime, timezone, timedelta

def seed_db():
    print("Setting up database...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    
    # Check if we already have transactions
    if db.query(Transaction).first():
        print("Database already seeded.")
        return
        
    print("Seeding with mock transactions...")
    
    now = datetime.now(timezone.utc)
    
    # User u123: Consistent bills but recent impulse buy
    transactions = [
        Transaction(user_id="u123", product_title="Netflix Subscription", price=15.49, category="Entertainment", timestamp=now - timedelta(days=2), is_recurring=True),
        Transaction(user_id="u123", product_title="Gym Membership", price=45.00, category="Health", timestamp=now - timedelta(days=5), is_recurring=True),
        Transaction(user_id="u123", product_title="Smart Speaker", price=199.99, category="Electronics", timestamp=now - timedelta(days=1), is_recurring=False),
        Transaction(user_id="u123", product_title="Electric Bill", price=85.00, category="Utilities", timestamp=now - timedelta(days=15), is_recurring=True),
        Transaction(user_id="u123", product_title="Groceries", price=120.50, category="Food", timestamp=now - timedelta(days=4), is_recurring=False),

        # User u124: Frugal saving for a car
        Transaction(user_id="u124", product_title="Spotify Premium", price=10.99, category="Entertainment", timestamp=now - timedelta(days=1), is_recurring=True),
        Transaction(user_id="u124", product_title="Car Insurance", price=115.00, category="Insurance", timestamp=now - timedelta(days=18), is_recurring=True),
        Transaction(user_id="u124", product_title="Groceries", price=65.20, category="Food", timestamp=now - timedelta(days=7), is_recurring=False),
        
        # User u125: High income luxury
        Transaction(user_id="u125", product_title="Designer Shoes", price=650.00, category="Clothing", timestamp=now - timedelta(days=3), is_recurring=False),
        Transaction(user_id="u125", product_title="Espresso Machine", price=1200.00, category="Home", timestamp=now - timedelta(days=10), is_recurring=False),
        Transaction(user_id="u125", product_title="Equinox Membership", price=250.00, category="Health", timestamp=now - timedelta(days=14), is_recurring=True),
        Transaction(user_id="u125", product_title="Fine Dining", price=320.00, category="Food", timestamp=now - timedelta(days=1), is_recurring=False),
    ]
    
    db.add_all(transactions)
    db.commit()
    print(f"Successfully added {len(transactions)} mock transactions.")
    
    db.close()

if __name__ == "__main__":
    seed_db()
