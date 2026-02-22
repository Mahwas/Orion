# Stripe Setup (Test Mode)

## Required Environment Variables

Add these to `backend/.env`:

```env
STRIPE_SECRET_KEY=sk_test_...          # From Stripe Dashboard → API keys
STRIPE_WEBHOOK_SECRET=whsec_...        # From Stripe CLI (see below)
STRIPE_CREDITS_PRICE_ID=price_...      # Price for "10 Analysis Credits"
STRIPE_PRO_PRICE_ID=price_...          # Price for "Orion Pro" subscription
FRONTEND_SUCCESS_URL=http://localhost:3000/success
FRONTEND_CANCEL_URL=http://localhost:3000/cancel
```

## Creating Prices in Stripe Dashboard

1. Go to [Stripe Dashboard → Products](https://dashboard.stripe.com/test/products) (Test mode)
2. **Credits pack:**
   - Click "Add product"
   - Name: `10 Analysis Credits`
   - Description: `One-time pack of 10 purchase analysis credits for Orion.`
   - Pricing: One-time, €5.00
   - Copy the Price ID (starts with `price_`) → set as `STRIPE_CREDITS_PRICE_ID`
3. **Orion Pro subscription:**
   - Click "Add product"
   - Name: `Orion Pro`
   - Description: `Unlimited AI purchase analyses.`
   - Pricing: Recurring, €9.99/month
   - Copy the Price ID → set as `STRIPE_PRO_PRICE_ID`

## Webhook Events Handled

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Credits: add `credits_per_pack × packs` to balance. Pro: set `pro_active=True` |
| `invoice.paid` | Re-activate Pro on subscription renewal |
| `customer.subscription.deleted` | Set `pro_active=False` |

## Local Testing with Stripe CLI

### 1. Install Stripe CLI

```bash
brew install stripe/stripe-cli/stripe
stripe login
```

### 2. Forward webhooks to local server

```bash
stripe listen --forward-to localhost:8000/stripe/webhook
```

Copy the `whsec_...` secret it prints and set `STRIPE_WEBHOOK_SECRET` in `.env`.

### 3. Start the backend

```bash
cd backend && source venv/bin/activate
uvicorn main:app --port 8000
```

### 4. Test: Credits Purchase

```bash
# Create checkout session
curl -X POST http://localhost:8000/billing/checkout/credits \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "demo_user_001"}'

# Response: {"checkout_session_id": "cs_test_...", "checkout_url": "https://checkout.stripe.com/..."}
# Open the checkout_url in browser, use test card 4242 4242 4242 4242, any future expiry, any CVC
# Stripe CLI will forward the webhook → credits added to demo_user_001
```

### 5. Test: Pro Subscription

```bash
curl -X POST http://localhost:8000/billing/checkout/pro \
  -H 'Content-Type: application/json' \
  -d '{"user_id": "demo_user_001"}'

# Same flow: open URL, pay with test card → pro_active=True
```

### 6. Test: Entitlement Enforcement

```bash
# Without credits or pro → 402
curl -X POST http://localhost:8000/api/v1/analyze \
  -H 'Content-Type: application/json' \
  -d '{
    "user_data": {"user_id": "demo_user_001", "monthly_income": 3000, "current_balance": 2500},
    "product_data": {"product_title": "Headphones", "price": 177.25, "category": "electronics"}
  }'
# → {"detail": "No analysis credits remaining. Buy a credits pack or upgrade to Orion Pro."}
```

### 7. Test: Failure Case (Declined Card)

Use test card `4000 0000 0000 0002` (always declined). The checkout will show an error on Stripe's page. No webhook is sent, so the backend is unaffected.

## Architecture

```
billing.py       → POST /billing/checkout/credits
                 → POST /billing/checkout/pro

webhooks.py      → POST /stripe/webhook (signature-verified, idempotent)

db_models.py     → StripeUser, Entitlement, WebhookEvent

routes.py        → POST /api/v1/analyze (entitlement-gated)
                 → POST /api/v1/analyze-demo (no gate, testing only)
```
