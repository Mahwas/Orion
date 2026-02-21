# Orion - AI Shopping Assistant

AI-powered Chrome extension that prevents impulsive online shopping by intercepting purchases at checkout.

## Quick Start

### Load the Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable **Developer mode** (top right toggle)
3. Click **Load unpacked**
4. Select the `extension/` folder

### Test It

1. Visit any e-commerce site (Amazon, eBay, etc.)
2. Add an item to cart
3. Click a checkout/purchase button
4. The Orion popup will appear with a "think before you buy" intervention

## Project Structure

```
Orion/
├── extension/          # Chrome extension (MV3)
│   ├── manifest.json   # Extension config
│   ├── content.js      # Checkout detection
│   ├── background.js   # Message handling
│   ├── popup.html      # Intervention UI
│   └── styles.css     # Styling
├── backend/            # FastAPI backend
│   ├── api/            # API routes
│   ├── core/           # AI agent
│   └── services/       # Plaid & Stripe
└── frontend/           # Next.js dashboard
```

## Features

- **Checkout Detection**: Monitors for checkout buttons on any e-commerce site
- **Positive Friction**: Intercepts purchases with a decision popup
- **Static Advice**: Shows budget-conscious questions before buying
- **Open Banking Ready**: Backend prepared for Plaid integration
- **Stripe Alternatives**: Ready to suggest cheaper alternatives

## Tech Stack

- Chrome Extension (MV3)
- FastAPI + OpenAI
- Next.js frontend
- Plaid (ready for integration)
