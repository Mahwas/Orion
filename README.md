# Orion

Orion Financial Agent — an AI-powered purchase analysis tool built with FastAPI and LangGraph.

---

## Stripe Setup (Test Mode)

### Required Environment Variables

Add these to `backend/.env`:

| Variable | Description | Example |
|---|---|---|
| `STRIPE_SECRET_KEY` | Stripe **test** secret key | `sk_test_51T2pnk...` |
| `STRIPE_WEBHOOK_SECRET` | Webhook signing secret (from Stripe CLI or Dashboard) | `whsec_...` |
| `STRIPE_CREDITS_PRICE_ID` | Price ID for the "10 Analysis Credits" product | `price_1Abc...` |
| `STRIPE_PRO_PRICE_ID` | Price ID for the "Orion Pro" subscription | `price_1Xyz...` |
| `FRONTEND_SUCCESS_URL` | Redirect after successful checkout | `http://localhost:3000/success` |
| `FRONTEND_CANCEL_URL` | Redirect after cancelled checkout | `http://localhost:3000/cancel` |

### Creating Products & Prices in Stripe Dashboard

1. Go to [Stripe Dashboard → Products](https://dashboard.stripe.com/test/products) (make sure **Test mode** is on)
2. **Credits pack**:
   - Click **+ Add product**
   - Name: `10 Analysis Credits`
   - Price: **€5.00**, **One-time**
   - After creating, copy the **Price ID** (starts with `price_`) → set as `STRIPE_CREDITS_PRICE_ID`
3. **Orion Pro subscription**:
   - Click **+ Add product**
   - Name: `Orion Pro`
   - Price: **€9.99/month**, **Recurring**
   - Copy the **Price ID** → set as `STRIPE_PRO_PRICE_ID`

### Webhook Event Types Handled

| Event | Action |
|---|---|
| `checkout.session.completed` | Credits: increment balance. Pro: activate subscription. |
| `invoice.paid` | Re-activate Pro on renewal (safety net) |
| `customer.subscription.deleted` | Deactivate Pro |

### Local Development with Stripe CLI

```bash
# 1. Install Stripe CLI (if needed)
brew install stripe/stripe-cli/stripe

# 2. Login to Stripe
stripe login

# 3. Forward webhooks to your local server
stripe listen --forward-to localhost:8000/stripe/webhook

# 4. Copy the webhook signing secret from the CLI output (whsec_...)
#    and set it as STRIPE_WEBHOOK_SECRET in backend/.env

# 5. Start the backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### Test Flows

#### 1. Credits Purchase

```bash
# Create checkout session
curl -X POST http://localhost:8000/billing/checkout/credits \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u123", "quantity": 1}'

# Open the returned checkout_url in browser
# Use test card: 4242 4242 4242 4242, any future expiry, any CVC
# Stripe CLI will forward the webhook → credits added to DB
```

#### 2. Pro Subscription

```bash
curl -X POST http://localhost:8000/billing/checkout/pro \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u123"}'

# Complete checkout with test card
# Webhook sets pro_active=True
```

#### 3. Declined Card (Failure Test)

```bash
# Use the same flow above but pay with test card:
# 4000 0000 0000 0002 (generic decline)
# Checkout fails on Stripe's side; no webhook is sent.
# Backend DB remains unchanged — no credits added, no Pro activated.
```

### API Endpoints Summary

| Method | Path | Description |
|---|---|---|
| `POST` | `/billing/checkout/credits` | Create credits checkout session |
| `POST` | `/billing/checkout/pro` | Create Pro subscription checkout session |
| `POST` | `/stripe/webhook` | Stripe webhook receiver |
| `POST` | `/api/v1/analyze` | Run purchase analysis (requires credits or Pro) |
| `GET` | `/api/v1/transactions/{user_id}` | Get user transaction history |
| `GET` | `/health` | Health check |
