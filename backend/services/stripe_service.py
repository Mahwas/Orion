import os
import stripe
from fastapi import HTTPException

# Need a sk_test token from Stripe dashboard
stripe.api_key = os.getenv("STRIPE_API_KEY", "mock_stripe_key")

def create_checkout(item_name: str, price_usd: float) -> str:
    """
    Creates a stripe checkout session for the given item.
    Returns the session URL.
    """
    if stripe.api_key == "mock_stripe_key":
        # Hackathon fallback if no keys
        return f"https://mock-stripe.com/checkout?item={item_name}&price={price_usd}"
    
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': item_name,
                    },
                    'unit_amount': int(price_usd * 100),  # cents
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url='http://localhost:3000/?stripe_success=true',
            cancel_url='http://localhost:3000/',
        )
        return session.url
    except Exception as e:
        print(f"Stripe error: {e}")
        raise HTTPException(status_code=500, detail="Payment gateway error")
